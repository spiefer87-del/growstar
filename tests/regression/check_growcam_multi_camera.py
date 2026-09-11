#!/usr/bin/env python3
"""Regression für beliebig viele getrennte GrowCam-Konfigurationen."""

import json
from pathlib import Path
import sys
import tempfile


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
    original_paths = (
        growcam.CONFIG_FILE, growcam.CAMERA_DIR,
        growcam.LATEST_IMAGE, growcam.TIMELAPSE_DIR,
    )
    original_configs = growcam.list_public_configs()
    original_config = dict(growcam._config)
    original_next_camera_number = growcam._next_camera_number
    original_run = growcam.subprocess.run
    original_which = growcam.shutil.which

    with tempfile.TemporaryDirectory(prefix="growstar-multicam-") as temp_dir:
        temp = Path(temp_dir)
        growcam.CONFIG_FILE = temp / "instance" / "growcam.json"
        growcam.CAMERA_DIR = temp / "instance" / "growcam"
        growcam.LATEST_IMAGE = growcam.CAMERA_DIR / "latest.jpg"
        growcam.TIMELAPSE_DIR = growcam.CAMERA_DIR / "timelapse"
        with growcam._config_lock:
            growcam._configs = {}
            growcam._config = {}

        try:
            growcam.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            growcam.CONFIG_FILE.write_text(json.dumps({
                "enabled": True,
                "host": "192.168.178.122",
                "tent_id": "tent_1",
                "name": "GrowCam Zelt 1",
            }), encoding="utf-8")
            first = growcam.load_config()
            require(
                first["camera_id"] == "camera_1"
                and len(growcam.list_public_configs()) == 1,
                "Bestehende Einzelkamera-Konfiguration wird automatisch übernommen",
            )
            second = growcam.create_camera({
                "enabled": True,
                "host": "192.168.178.123",
                "tent_id": "tent_2",
                "name": "GrowCam Zelt 2",
            })
            registry = json.loads(growcam.CONFIG_FILE.read_text(encoding="utf-8"))
            require(
                first["camera_id"] == "camera_1"
                and second["camera_id"] == "camera_2"
                and registry["version"] == 2
                and len(registry["cameras"]) == 2,
                "Registry vergibt stabile Kamera-IDs ohne feste Obergrenze",
            )
            require(
                growcam.camera_for_tent("tent_1")["camera_id"] == "camera_1"
                and growcam.camera_for_tent("tent_2")["camera_id"] == "camera_2",
                "Jede Station findet ausschließlich ihre zugewiesene Kamera",
            )

            def fake_run(command, **_kwargs):
                Image.new("RGB", (320, 180), color=(20, 80, 40)).save(
                    command[-1], format="JPEG"
                )
                return type("Result", (), {"returncode": 0, "stderr": ""})()

            growcam.shutil.which = lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None
            growcam.subprocess.run = fake_run
            growcam.save_config({
                **first, "batch_id": 7, "timelapse_enabled": True,
            }, camera_id="camera_1")
            growcam.save_config({
                **second, "batch_id": 7, "timelapse_enabled": True,
            }, camera_id="camera_2")
            one = growcam.capture_snapshot(archive=True, camera_id="camera_1")
            two = growcam.capture_snapshot(archive=True, camera_id="camera_2")
            archive = growcam.list_all_timelapse_frames()
            require(
                one["success"] and two["success"]
                and growcam.latest_image_path("camera_1").is_file()
                and growcam.latest_image_path("camera_2").is_file()
                and growcam.latest_image_path("camera_1") != growcam.latest_image_path("camera_2")
                and archive["total"] == 2
                and {item["camera_id"] for item in archive["items"]}
                == {"camera_1", "camera_2"},
                "Standbilder, Archive und Laufzeitstatus werden pro Kamera getrennt",
            )

            routes = (ROOT / "routes/camera.py").read_text(encoding="utf-8")
            hardware = (ROOT / "templates/devices.html").read_text(encoding="utf-8")
            camera_page = (ROOT / "templates/plants/camera.html").read_text(encoding="utf-8")
            dashboard = (ROOT / "routes/dashboard.py").read_text(encoding="utf-8")
            require(
                "growcam_hardware_add" in routes
                and "Kamera hinzufügen und aktivieren" in hardware
                and "camera_id" in hardware
                and "camera_id" in camera_page
                and "growcam_for_tent(tent_id)" in dashboard,
                "Hardware-Manager, Medienseite und Stationsdashboard sind mehrkamerafähig",
            )
            require(
                permission_requirement("/devices/growcam/hinzufuegen", "POST").permissions
                == ("hardware.configure",),
                "Hinzufügen bleibt auf Hardware-Konfiguration beschränkt",
            )

            third = growcam.create_camera({
                "enabled": True,
                "host": "192.168.178.124",
                "tent_id": "tent_3",
            })
            require(
                len(growcam.list_public_configs()) == 3
                and third["camera_id"] == "camera_3",
                "Weitere Stationen erhalten ohne Codeänderung fortlaufende Kamera-IDs",
            )
        finally:
            growcam.shutil.which = original_which
            growcam.subprocess.run = original_run
            (
                growcam.CONFIG_FILE, growcam.CAMERA_DIR,
                growcam.LATEST_IMAGE, growcam.TIMELAPSE_DIR,
            ) = original_paths
            with growcam._config_lock:
                growcam._configs = {
                    item["camera_id"]: dict(item) for item in original_configs
                }
                growcam._config = original_config
                growcam._next_camera_number = original_next_camera_number

    print("✅ GrowCam-Mehrkamera-Verwaltung vollständig geprüft")


if __name__ == "__main__":
    main()
