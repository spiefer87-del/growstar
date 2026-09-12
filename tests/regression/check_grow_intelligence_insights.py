#!/usr/bin/env python3
"""Regression für stationsbezogene Grow-Intelligence-Erkenntnisse."""

import tempfile
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import grow_events
from services.grow_insights import build_insights


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def add_event(**overrides):
    data = {
        "station_id": "tent_1",
        "occurred_at": 1_700_099_000,
        "category": "system",
        "event_type": "test_event",
        "severity": "info",
        "title": "Testereignis",
        "source": "regression",
    }
    data.update(overrides)
    return grow_events.record_event(**data)


def main():
    original_db = grow_events.DB_FILE
    now = 1_700_100_000
    with tempfile.TemporaryDirectory(prefix="growstar-insights-") as temp_dir:
        grow_events.DB_FILE = Path(temp_dir) / "events.db"
        try:
            grow_events.init_grow_event_db()
            empty = build_insights(now=now, since=now - 7 * 86400)
            require(
                empty["state"] == "collecting"
                and empty["items"][0]["kind"] == "collecting",
                "Eine neue Installation erklärt die noch wachsende Datenbasis",
            )

            device_id = add_event(
                occurred_at=now - 1000,
                category="device",
                event_type="alarm_opened",
                severity="critical",
                title="Ventilator nicht erreichbar",
                correlation_id="alarm:tent_1:vent:1",
            )
            climate_id = add_event(
                occurred_at=now - 700,
                category="climate",
                event_type="alarm_opened",
                severity="warning",
                title="Temperatur erhöht",
                correlation_id="alarm:tent_1:temp:1",
            )
            add_event(
                occurred_at=now - 600,
                category="climate",
                event_type="alarm_recovered",
                severity="success",
                title="Entwarnung: Temperatur normal",
                correlation_id="alarm:tent_1:temp:1",
            )
            add_event(
                occurred_at=now - 500,
                category="system",
                event_type="day_night_profile_changed",
                title="Tagprofil aktiv",
                source="profile_scheduler",
            )
            add_event(
                occurred_at=now - 8 * 86400,
                category="media",
                event_type="plant_photo_created",
                severity="success",
                title="Pflanzenfoto gespeichert",
                source="plant_management",
            )
            add_event(
                station_id="tent_2",
                occurred_at=now - 100,
                category="device",
                event_type="alarm_opened",
                severity="critical",
                title="Pumpe Zelt 2 nicht erreichbar",
                correlation_id="alarm:tent_2:pump:1",
            )

            result = build_insights(
                station_id="tent_1",
                since=now - 7 * 86400,
                station_names={"tent_1": "Zelt 1", "tent_2": "Zelt 2"},
                now=now,
            )
            kinds = {item["kind"] for item in result["items"]}
            require(
                result["state"] == "attention" and result["open_count"] == 1,
                "Nur der nicht entwarnte Watchdog-Vorgang bleibt offen",
            )
            require(
                {"open_alarm", "temporal_correlation", "recoveries", "profile", "photo_age"}.issubset(kinds),
                "Erkenntnisse decken Vorgänge, Zusammenhang, Entwarnung, Profil und Fotodokumentation ab",
            )
            correlation = next(
                item for item in result["items"] if item["kind"] == "temporal_correlation"
            )
            require(
                set(correlation["evidence_ids"]) == {device_id, climate_id}
                and "keine bestätigte Ursache" in correlation["summary"],
                "Zeitlicher Zusammenhang nennt Belege und behauptet keine Kausalität",
            )
            require(
                all(item.get("station_id") != "tent_2" for item in result["items"]),
                "Stationsfilter vermischt Zelt 1 und Zelt 2 nicht",
            )
            require(
                any(item["station_label"] == "Zelt 1" for item in result["items"]),
                "Erkenntnisse verwenden den lesbaren Stationsnamen",
            )
        finally:
            grow_events.DB_FILE = original_db

    route_source = (ROOT / "routes/events.py").read_text(encoding="utf-8")
    template = (ROOT / "templates/grow_events.html").read_text(encoding="utf-8")
    require(
        "build_insights(" in route_source and "station_id=station_id" in route_source,
        "Timeline reicht die aktive Station an die Erkenntnislogik weiter",
    )
    require(
        "Aktuelle Erkenntnisse" in template
        and "keine automatisch bestätigten Ursachen" in template
        and "insight.evidence_ids" in template
        and 'insights["items"]' in template
        and "insights.items" not in template,
        "Oberfläche kennzeichnet Hinweise, Belege und Grenzen der Analyse",
    )

    print("✅ INTELLIGENCE.INSIGHTS.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
