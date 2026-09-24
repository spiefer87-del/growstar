#!/usr/bin/env python3
"""Regression for anchored GrowCam archive times and accordion controls."""

from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from services import growcam


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def local_timestamp(hour, minute, second=0):
    return datetime(2026, 9, 24, hour, minute, second).timestamp()


def main():
    config = growcam._normalize_config({"batch_id": 7, "timelapse_start_time": "08:15", "timelapse_interval_sec": 3600})
    require(config["timelapse_start_time"] == "08:15", "Fester Zeitanker wird gespeichert")
    require(growcam._normalize_config({"batch_id": 7})["timelapse_start_time"] == "", "Bestehende Kameras behalten zunächst ihren bisherigen Rhythmus")
    for invalid in ("08:60", "24:00", "08:15:30", "morgen"):
        try:
            growcam._normalize_config({"batch_id": 7, "timelapse_start_time": invalid})
        except ValueError:
            pass
        else:
            raise AssertionError("Ungültige Uhrzeit akzeptiert: " + invalid)
    require(growcam.next_timelapse_capture(local_timestamp(8, 14, 59), 3600, "08:15") == local_timestamp(8, 15), "Um 08:15 ist der erste Stundentermin fällig")
    require(growcam.next_timelapse_capture(local_timestamp(8, 15), 3600, "08:15") == local_timestamp(9, 15), "Nach einem Termin folgt die nächste Stunde zur gleichen Minute")
    require(growcam.next_timelapse_capture(local_timestamp(8, 47), 3600, "08:15") == local_timestamp(9, 15), "Zwischen den Terminen wird nicht zusätzlich archiviert")
    require(growcam.next_timelapse_capture(local_timestamp(8, 16), 300, "08:15") == local_timestamp(8, 20), "Minutenintervalle orientieren sich ebenfalls am Anker")
    require(growcam.next_timelapse_capture(local_timestamp(20, 16), 21600, "08:15") == datetime(2026, 9, 25, 2, 15).timestamp(), "Sechsstündige Termine bleiben über Mitternacht ausgerichtet")
    template = (ROOT / "templates/plants/timelapse.html").read_text(encoding="utf-8")
    routes = (ROOT / "routes/camera.py").read_text(encoding="utf-8")
    require(template.count('name="timelapse-sections"') >= 4 and 'other.open = false' in template, "Aufnahmeplan, Videos, Erstellung und Bilder schließen sich gegenseitig")
    require(template.index('growcam_timelapse_toggle') < template.index('id="timelapse-plan"') and 'name="timelapse_enabled"' not in template, "Zeitraffer-Schalter steht außerhalb des Aufnahmeplans")
    require('name="timelapse_start_time"' in template and '"timelapse_start_time": request.form.get' in routes, "Die gewählte Uhrzeit erreicht die Konfiguration")
    print("✅ GROWCAM.TIMELAPSE-SCHEDULE.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
