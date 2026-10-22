"""Camera failures, scheduled archive gaps and recoveries."""

import tempfile
import time
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services import growcam
from services import alerts
from services.alerts import extract_alarm_candidates


def main():
    now = time.time()
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        configs = [
            {**growcam._normalize_config({"camera_id": "camera_1", "enabled": True,
                "host": "192.168.1.10", "tent_id": "tent_1", "batch_id": 1,
                "timelapse_enabled": True}, "camera_1")},
            {**growcam._normalize_config({"camera_id": "camera_2", "enabled": True,
                "host": "192.168.1.11", "tent_id": "tent_2",
                "timelapse_enabled": False}, "camera_2")},
        ]
        files = {c["camera_id"]: root / c["camera_id"] / "latest.jpg" for c in configs}
        for image in files.values():
            image.parent.mkdir()
            image.write_bytes(b"picture")
        files["camera_1"].touch()
        import os
        os.utime(files["camera_1"], (now - 900, now - 900))
        os.utime(files["camera_2"], (now - 10, now - 10))
        statuses = {"camera_1": {"last_capture": None, "last_error": "401 Unauthorized",
                                 "consecutive_failures": 4},
                    "camera_2": {"last_capture": None, "last_error": None,
                                 "consecutive_failures": 0}}
        def schedule(config, **kwargs):
            return {"state": "running" if config["camera_id"] == "camera_1" else "disabled",
                    "last_archived_at": now - 3600 if config["camera_id"] == "camera_1" else None,
                    "interval_sec": 900}

        with patch.object(growcam, "list_public_configs", return_value=configs), \
                patch.object(growcam, "latest_image_path", side_effect=lambda cid: files[cid]), \
                patch.object(growcam, "_status_for", side_effect=lambda cid: statuses[cid]), \
                patch.object(growcam, "timelapse_schedule_snapshot", side_effect=schedule):
            cameras = growcam.camera_health_snapshot(now=now)
            assert cameras[0]["stale"] and cameras[0]["archive_stale"]
            assert cameras[1]["state"] == "ok" and not cameras[1]["archive_stale"]
            candidates = extract_alarm_candidates({"cameras": cameras, "stations": []})
            assert "camera:camera_1:stale" in candidates
            assert "camera:camera_1:archive_stale" in candidates
            assert not any("camera_2" in key for key in candidates)
            os.utime(files["camera_1"], (now, now))
            statuses["camera_1"] = {"last_capture": now, "last_error": None,
                                    "consecutive_failures": 0}
            cameras = growcam.camera_health_snapshot(now=now)
            assert not cameras[0]["stale"]
            assert "camera:camera_1:stale" not in extract_alarm_candidates(
                {"cameras": cameras, "stations": []})

        assert growcam._rtsp_url(configs[0]).startswith("rtsp://admin:@")
        delivered = []
        with patch.object(alerts, "_STATE_LOADED", True), \
                patch.object(alerts, "_ENGINE_STARTED_AT", now - 1000), \
                patch.object(alerts, "_ACTIVE", {}), \
                patch.object(alerts, "_HISTORY", []), \
                patch.object(alerts, "_atomic_save"), \
                patch.object(alerts, "_timeline_alarm"), \
                patch.object(alerts, "_notifications_available", return_value=True), \
                patch.object(alerts, "load_notification_settings", return_value={"send_recovery": True, "repeat_minutes": 60}), \
                patch.object(alerts, "enqueue_notification", side_effect=lambda message, **kw: delivered.append((message, kw)) or True):
            failed = {"camera_id": "camera_1", "tent_id": "tent_1", "name": "Zeltkamera",
                      "stale": True, "archive_stale": False, "age": 900,
                      "last_capture": now - 900, "last_error": "401 Unauthorized"}
            alerts.process_watchdog_snapshot({"cameras": [failed], "stations": []}, now=now)
            assert len(delivered) == 1 and "401 Unauthorized" in delivered[0][0]
            alerts.process_watchdog_snapshot({"cameras": [failed], "stations": []}, now=now + 5)
            assert len(delivered) == 1
            alerts.process_watchdog_snapshot({"cameras": [], "stations": []}, now=now + 10)
            assert len(delivered) == 1, "Deaktivierung ist keine erfolgreiche Aufnahme"
            alerts.process_watchdog_snapshot({"cameras": [failed], "stations": []}, now=now + 15)
            fresh = {**failed, "stale": False, "last_capture": now + 20, "last_error": None}
            alerts.process_watchdog_snapshot({"cameras": [fresh], "stations": []}, now=now + 20)
            assert len(delivered) == 3 and "wieder aktiv" in delivered[-1][0]
    print("Camera health alerts and recovery OK")


if __name__ == "__main__":
    main()
