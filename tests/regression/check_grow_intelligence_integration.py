#!/usr/bin/env python3
"""Regression für die ersten produktiven Grow-Intelligence-Quellen."""

import tempfile
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import alerts, grow_events


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    original_db = grow_events.DB_FILE
    with tempfile.TemporaryDirectory(prefix="growstar-intelligence-") as temp_dir:
        grow_events.DB_FILE = Path(temp_dir) / "events.db"
        try:
            grow_events.init_grow_event_db()

            require(
                grow_events.enqueue_event(
                    station_id="tent_1",
                    category="system",
                    event_type="queue_probe",
                    severity="info",
                    title="Queue-Test",
                    source="regression",
                    dedupe_key="regression:queue-probe",
                ),
                "Produktionsereignisse werden ohne blockierenden DB-Zugriff angenommen",
            )
            require(
                grow_events.event_queue_status()["queued"] >= 1,
                "Event-Queue meldet wartende Einträge",
            )
            grow_events.flush_event_queue(limit=1000)
            stored = grow_events.list_events(station_id="tent_1", since=0)
            require(
                any(item["event_type"] == "queue_probe" for item in stored["items"]),
                "Event-Writer persistiert wartende Einträge",
            )

            alarm = {
                "key": "hardware:tent_1:vent",
                "rule": "hardware",
                "severity": "critical",
                "title": "Ventilator nicht erreichbar",
                "detail": "Der konfigurierte Aktor antwortet nicht.",
                "station": "tent_1",
                "station_name": "Zelt 1",
                "first_seen": 1_700_000_000,
            }
            alerts._timeline_alarm(alarm, kind="opened", now=1_700_000_000)
            alerts._timeline_alarm(alarm, kind="recovered", now=1_700_000_125)
            grow_events.flush_event_queue(limit=1000)
            alarm_events = [
                item for item in grow_events.list_events(
                    station_id="tent_1", category="device", since=0
                )["items"]
                if item["source"] == "watchdog"
            ]
            require(
                len(alarm_events) == 2
                and {item["event_type"] for item in alarm_events}
                == {"alarm_opened", "alarm_recovered"},
                "Watchdog protokolliert Alarm und Entwarnung",
            )
            require(
                len({item["correlation_id"] for item in alarm_events}) == 1
                and {item["severity"] for item in alarm_events}
                == {"critical", "success"},
                "Alarm und Entwarnung bleiben als Vorgang verknüpft",
            )

            grow_events.DB_FILE = Path(temp_dir) / "missing" / "events.db"
            grow_events.enqueue_event(
                category="system",
                event_type="failure_probe",
                title="Fehlerisolation",
                source="regression",
            )
            grow_events.flush_event_queue(limit=1000)
            require(
                grow_events.event_queue_status()["queued"] == 0,
                "Fehler im Timeline-Speicher bleiben von den Produzenten isoliert",
            )
        finally:
            grow_events.DB_FILE = original_db

    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    profile_source = (ROOT / "core/profile.py").read_text(encoding="utf-8")
    energy_source = (ROOT / "services/energy.py").read_text(encoding="utf-8")
    plant_source = (ROOT / "routes/plant_management.py").read_text(encoding="utf-8")
    camera_route_source = (ROOT / "routes/camera.py").read_text(encoding="utf-8")
    growcam_source = (ROOT / "services/growcam.py").read_text(encoding="utf-8")
    template = (ROOT / "templates/grow_events.html").read_text(encoding="utf-8")

    require(
        '"growstar-events"' in app_source
        and "grow_event_writer_loop" in app_source,
        "App startet einen eigenen Grow-Intelligence-Writer",
    )
    require(
        "day_night_profile_changed" in profile_source
        and "grow_profile_applied" in (ROOT / "routes/profile.py").read_text(encoding="utf-8"),
        "Automatische und manuelle Profilwechsel sind angebunden",
    )
    require(
        "energy_day_reset" in energy_source and "energy_total_reset" in energy_source,
        "Energie-Tages- und Gesamtreset sind angebunden",
    )
    require(
        all(token in plant_source for token in (
            "plant_stage_changed", "plant_status_changed",
            "plant_photo_created", "batch_photo_created",
        )),
        "Pflanzenzustände und Fotos sind angebunden",
    )
    require(
        "timelapse_plan_activated" in camera_route_source
        and "timelapse_video_created" in growcam_source
        and "camera_recording_created" in growcam_source,
        "Zeitrafferpläne, Zeitraffervideos und Aufnahmen sind angebunden",
    )
    require(
        "Event-Writer" in template and "zusammengehöriger Vorgang" in template,
        "Timeline macht Quellenstatus und Korrelation sichtbar",
    )

    print("✅ Grow Intelligence Quellenintegration vollständig geprüft")


if __name__ == "__main__":
    main()
