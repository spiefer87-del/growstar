#!/usr/bin/env python3
"""Regression für lesbare Vorher-/Nachher-Ereignisse bei Einstellungen."""

import tempfile
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config_update import apply_config_patch
from core.runtime import create_isolated_runtime
from services import grow_events


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    described = grow_events.describe_setting_changes({
        "DAY_TEMP": {"before": 25.0, "after": 25.2},
        "DAY_START_MIN": {"before": 360, "after": 390},
        "WIFI_PASSWORD": {"before": "alt", "after": "neu"},
    })
    require(
        [item["key"] for item in described] == ["DAY_START_MIN", "DAY_TEMP"],
        "Nur freigegebene, nicht geheime Einstellungen werden beschrieben",
    )
    require(
        any("25 °C → 25,2 °C" in item["text"] for item in described)
        and any("06:00 Uhr → 06:30 Uhr" in item["text"] for item in described),
        "Zahlen und Profilzeiten werden mit Einheiten verständlich formatiert",
    )

    runtime = create_isolated_runtime(
        "tent_change_test",
        config_data={"DAY_TEMP": 25.0},
        save_config_callback=lambda cfg: None,
    )
    result = apply_config_patch({"DAY_TEMP": 25.2}, runtime=runtime)
    require(
        result["changed_keys"] == ["DAY_TEMP"]
        and result["changes"]["DAY_TEMP"] == {"before": 25.0, "after": 25.2},
        "Atomarer Config-Pfad liefert tatsächliche Vorher-/Nachher-Werte",
    )

    original_db = grow_events.DB_FILE
    with tempfile.TemporaryDirectory(prefix="growstar-setting-events-") as temp_dir:
        grow_events.DB_FILE = Path(temp_dir) / "events.db"
        try:
            grow_events.init_grow_event_db()
            queued = grow_events.enqueue_setting_change_event(
                station_id="tent_1",
                changes=result["changes"],
                title="Stationswerte geändert: Zelt 1",
                event_type="station_settings_updated",
                source="station_config",
                source_id="tent_1",
            )
            grow_events.flush_event_queue(limit=100)
            events = grow_events.list_events(station_id="tent_1", since=0)["items"]
            event = next(item for item in events if item["event_type"] == "station_settings_updated")
            require(
                queued is True
                and "Tag-Solltemperatur: 25 °C → 25,2 °C" in event["summary"]
                and event["category"] == "climate"
                and event["metadata"]["geändert"] == 1,
                "Ein Speichervorgang erzeugt ein kompaktes Klima-Ereignis",
            )
            require(
                grow_events.enqueue_setting_change_event(
                    station_id="tent_1",
                    changes={"DAY_TEMP": {"before": 25.2, "after": 25.2}},
                    title="Ohne Änderung",
                    source="regression",
                ) is False,
                "Unverändertes Speichern erzeugt kein Timeline-Rauschen",
            )
        finally:
            grow_events.DB_FILE = original_db

    tent_routes = (ROOT / "routes/tents.py").read_text(encoding="utf-8")
    legacy_route = (ROOT / "routes/config.py").read_text(encoding="utf-8")
    require(
        tent_routes.count("enqueue_setting_change_event(") >= 2
        and "profile_changes" in tent_routes,
        "Stationswerte und Profilvorlagen verwenden dieselbe Änderungsdarstellung",
    )
    require(
        "enqueue_setting_change_event(" in legacy_route,
        "Legacy-Konfigurationsroute für Zelt 1 bleibt ebenfalls angebunden",
    )

    print("✅ INTELLIGENCE.CHANGES.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
