#!/usr/bin/env python3
"""Regressionstest für die lokale VIVOSUN-GrowCam-C4-Anbindung."""

from pathlib import Path
import tempfile
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image

from auth.policy import permission_requirement
import services.growcam as growcam


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    original_paths = growcam.CONFIG_FILE, growcam.CAMERA_DIR, growcam.LATEST_IMAGE
    original_which = growcam.shutil.which
    original_run = growcam.subprocess.run
    original_config = growcam.public_config()
    captured_command = []

    with tempfile.TemporaryDirectory(prefix="growstar-growcam-") as temp_dir:
        temp = Path(temp_dir)
        growcam.CONFIG_FILE = temp / "instance" / "growcam.json"
        growcam.CAMERA_DIR = temp / "instance" / "growcam"
        growcam.LATEST_IMAGE = growcam.CAMERA_DIR / "latest.jpg"

        def fake_run(command, **kwargs):
            captured_command[:] = command
            Image.effect_noise((320, 180), 70).convert("RGB").save(
                command[-1], format="JPEG", quality=90
            )

            class Result:
                returncode = 0
                stderr = ""

            require(kwargs.get("timeout") == 30, "FFmpeg-Aufruf besitzt ein festes Zeitlimit")
            return Result()

        try:
            try:
                growcam.save_config({
                    "enabled": True,
                    "host": "8.8.8.8",
                    "tent_id": "tent_1",
                })
            except ValueError:
                pass
            else:
                raise AssertionError("Öffentliche Kamera-IP wurde akzeptiert")
            print("✅ GrowCam akzeptiert ausschließlich lokale IPv4-Adressen")

            config = growcam.save_config({
                "enabled": True,
                "name": "VIVOSUN Kellerkamera",
                "host": "192.168.178.122",
                "port": 554,
                "path": "/live/ch00_0",
                "username": "admin",
                "interval_sec": 60,
                "tent_id": "tent_1",
            })
            require(
                config["host"] == "192.168.178.122"
                and config["path"] == "/live/ch00_0",
                "Bestätigte GrowCam-C4-Verbindungsdaten werden gespeichert",
            )
            config_text = growcam.CONFIG_FILE.read_text(encoding="utf-8")
            require(
                "password" not in config_text.lower()
                and "rtsp://" not in config_text.lower(),
                "Konfiguration speichert weder Passwort noch vollständige RTSP-URL",
            )

            growcam.shutil.which = lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None
            growcam.subprocess.run = fake_run
            result = growcam.capture_snapshot()
            require(
                result["success"] is True
                and result["width"] == 320
                and result["height"] == 180
                and result["capturing"] is False
                and growcam.LATEST_IMAGE.is_file(),
                "Snapshot wird validiert, atomar veröffentlicht und korrekt gemeldet",
            )
            require(
                "-rtsp_transport" in captured_command
                and "tcp" in captured_command
                and "rtsp://admin:@192.168.178.122:554/live/ch00_0" in captured_command,
                "FFmpeg liest den bestätigten lokalen RTSP-Stream über TCP",
            )

            read_requirement = permission_requirement(
                "/pflanzenmanagement/kamera", "GET"
            )
            write_requirement = permission_requirement(
                "/pflanzenmanagement/kamera/aufnahme", "POST"
            )
            api_requirement = permission_requirement(
                "/api/plant-management/camera/status", "GET"
            )
            require(
                read_requirement.permissions == ("plants.view",)
                and api_requirement.permissions == ("plants.view",)
                and write_requirement.permissions == ("plants.edit",),
                "Kamerabild, Status und Bedienung sind rollenbasiert geschützt",
            )

            app_source = (ROOT / "app.py").read_text(encoding="utf-8")
            template = (ROOT / "templates/plants/camera.html").read_text(encoding="utf-8")
            require(
                "register_camera_routes(app)" in app_source
                and '"growstar-growcam"' in app_source
                and "growcam_image" in template,
                "Route, Hintergrundaufnahme und Kameraansicht sind vollständig eingebunden",
            )
        finally:
            growcam.shutil.which = original_which
            growcam.subprocess.run = original_run
            growcam.CONFIG_FILE, growcam.CAMERA_DIR, growcam.LATEST_IMAGE = original_paths
            with growcam._config_lock:
                growcam._config = original_config

    print("✅ VIVOSUN GrowCam C4 Integration vollständig erfolgreich")


if __name__ == "__main__":
    main()
