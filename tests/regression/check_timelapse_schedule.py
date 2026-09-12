#!/usr/bin/env python3
"""Regression für neustartfeste GrowCam-Zeitrafferpläne."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import services.growcam as growcam


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    start = 2_000_000_000
    hour = 3600
    base = {
        "camera_id": "camera_1",
        "enabled": True,
        "host": "192.168.178.122",
        "tent_id": "tent_1",
        "batch_id": 7,
        "timelapse_enabled": True,
        "timelapse_interval_sec": hour,
        "timelapse_start_at": start,
        "timelapse_end_at": start + 3 * hour + 900,
    }

    normalized = growcam._normalize_config(base)
    require(
        normalized["timelapse_start_at"] == start
        and normalized["timelapse_end_at"] == start + 3 * hour + 900,
        "Start und letztes Bild werden dauerhaft als Wandzeit normalisiert",
    )

    upcoming = growcam.timelapse_schedule_snapshot(
        normalized, now=start - 60, last_archived_at=None
    )
    require(
        upcoming["state"] == "upcoming"
        and upcoming["next_capture_at"] == start
        and not upcoming["capture_due"],
        "Vor dem Start wartet der Plan exakt auf den ersten gespeicherten Slot",
    )

    after_restart = growcam.timelapse_schedule_snapshot(
        normalized, now=start + 1800, last_archived_at=start + 3
    )
    require(
        not after_restart["capture_due"]
        and after_restart["next_capture_at"] == start + hour,
        "Ein App-Neustart verschiebt den nächsten Stunden-Slot nicht",
    )

    missed = growcam.timelapse_schedule_snapshot(
        normalized, now=start + 2 * hour + 120, last_archived_at=start + 3
    )
    require(
        missed["capture_due"]
        and missed["due_at"] == start + 2 * hour,
        "Nach einer Pause wird nur der letzte fällige Slot aufgenommen",
    )

    final = growcam.timelapse_schedule_snapshot(
        normalized,
        now=normalized["timelapse_end_at"] + 5,
        last_archived_at=start + 3 * hour,
    )
    require(
        final["capture_due"]
        and final["due_at"] == normalized["timelapse_end_at"]
        and final["state"] == "finishing"
        and final["planned_images"] == 5,
        "Ein abweichender Endzeitpunkt erzeugt genau eine Abschlussaufnahme",
    )

    completed = growcam.timelapse_schedule_snapshot(
        normalized,
        now=normalized["timelapse_end_at"] + 61,
        last_archived_at=start + 3 * hour,
    )
    require(
        completed["state"] == "completed"
        and not completed["capture_due"]
        and completed["next_capture_at"] is None,
        "Nach dem kurzen Endslot-Fenster bleibt ein abgeschlossener Plan beendet",
    )

    template = (ROOT / "templates/plants/timelapse.html").read_text(encoding="utf-8")
    route = (ROOT / "routes/camera.py").read_text(encoding="utf-8")
    service = (ROOT / "services/growcam.py").read_text(encoding="utf-8")
    require(
        'name="timelapse_start_at"' in template
        and 'name="timelapse_end_at"' in template
        and "Nächstes Bild" in template
        and "Letzte Aufnahme" in template
        and "Geplanter Umfang" in template,
        "Zeitrafferseite zeigt Zeitraum, letzten und nächsten Slot sowie Umfang",
    )
    require(
        '"timelapse_start_at": start_at' in route
        and '"timelapse_end_at": end_at' in route
        and "time.monotonic()" in service
        and "wall_now = time.time()" in service,
        "Route persistiert den Plan und der Scheduler trennt Vorschau- von Wandzeit",
    )

    print("✅ MEDIA.TIMELAPSE.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
