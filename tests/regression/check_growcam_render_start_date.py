#!/usr/bin/env python3
"""Render selection uses the chosen local start day and isolates its frame set."""

from pathlib import Path
import os
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import services.growcam as growcam


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    original = (growcam.TIMELAPSE_DIR, growcam.public_config, growcam.shutil.which, growcam.subprocess.run)
    try:
        with tempfile.TemporaryDirectory(prefix="growcam-start-date-") as temp:
            growcam.TIMELAPSE_DIR = Path(temp)
            growcam.public_config = lambda camera_id=None: {
                "camera_id": "camera_1", "batch_id": 17, "video_retention_count": 25,
            }
            growcam.shutil.which = lambda command: "/usr/bin/ffmpeg"
            batch = growcam._batch_dir(17, "camera_1")
            batch.mkdir(parents=True)
            days = [("2026-09-20", 1), ("2026-09-21", 2), ("2026-09-22", 2)]
            for day, count in days:
                for index in range(count):
                    frame = batch / f"frame-{day.replace('-', '')}T12000{index}Z-000000.jpg"
                    frame.write_bytes(b"frame")
                    timestamp = time.mktime(time.strptime(f"{day} 12:00:0{index}", "%Y-%m-%d %H:%M:%S"))
                    os.utime(frame, (timestamp, timestamp))
            require(growcam.timelapse_frame_days(17) == dict(days), "Bildanzahl je lokalem Tag wird angezeigt")
            for bad in ("2026-02-30", "yesterday", "2026-09-22;echo hi"):
                require(not growcam.start_timelapse_render({"start_date": bad})["success"], "Ungültiges Datum wird abgewiesen")
            require(not growcam.start_timelapse_render({"start_date": "2026-09-23"})["success"], "Start ohne zwei Bilder wird abgewiesen")

            calls = []
            def fake_run(command, **kwargs):
                source = Path(command[command.index("-i") + 1]).parent
                calls.append(sorted(frame.name for frame in source.glob("frame-*.jpg")))
                Path(command[-1]).write_bytes(b"video")
                return SimpleNamespace(returncode=0, stderr="")
            growcam.subprocess.run = fake_run
            for start, expected in (("2026-09-21", 4), ("", 5)):
                result = growcam.start_timelapse_render({"start_date": start})
                require(result["success"] and result["frame_count"] == expected, "Renderauftrag zählt nur ausgewählte Bilder")
                for _ in range(100):
                    if not growcam.status_snapshot()["timelapse_rendering"]:
                        break
                    time.sleep(.02)
                require(len(calls[-1]) == expected and growcam.status_snapshot()["timelapse_total_frames"] == expected, "FFmpeg erhält genau die ausgewählten Bilder")
            require(not list(batch.glob(".timelapse-selection-*")), "Temporäre Bildauswahl wird bereinigt")

        template = (ROOT / "templates/plants/timelapse.html").read_text(encoding="utf-8")
        require('name="start_date"' in template and 'id="video-create"' in template and 'id="timelapse-frames"' in template, "Videoerstellung und Bildarchiv sind getrennt")
        require('video.created_at' in template and 'latest_video_mtime' in template, "Erstellungsdatum steht bei letzten Videos")
    finally:
        growcam.TIMELAPSE_DIR, growcam.public_config, growcam.shutil.which, growcam.subprocess.run = original
    print("✅ GROWCAM.RENDER-START-DATE.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
