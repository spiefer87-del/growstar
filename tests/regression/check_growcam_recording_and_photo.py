#!/usr/bin/env python3
"""Regression für Videoaufnahme, Zeitraffer-Modul und GrowCam-Pflanzenfoto."""

from pathlib import Path
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
    original_next = growcam._next_camera_number
    original_run = growcam.subprocess.run
    original_which = growcam.shutil.which
    command = []

    with tempfile.TemporaryDirectory(prefix="growstar-recording-") as temp_dir:
        temp = Path(temp_dir)
        growcam.CONFIG_FILE = temp / "instance" / "growcam.json"
        growcam.CAMERA_DIR = temp / "instance" / "growcam"
        growcam.LATEST_IMAGE = growcam.CAMERA_DIR / "latest.jpg"
        growcam.TIMELAPSE_DIR = growcam.CAMERA_DIR / "timelapse"
        with growcam._config_lock:
            growcam._configs = {}
            growcam._config = {}
            growcam._next_camera_number = 1

        def fake_run(args, **kwargs):
            command[:] = args
            Path(args[-1]).write_bytes(b"video" * 1024)
            require(kwargs.get("timeout") == 60, "30-Sekunden-Aufnahme besitzt ein festes Zeitlimit")
            return type("Result", (), {"returncode": 0, "stderr": ""})()

        try:
            camera = growcam.create_camera({
                "enabled": True,
                "host": "192.168.178.122",
                "tent_id": "tent_1",
            })
            growcam.shutil.which = lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None
            growcam.subprocess.run = fake_run
            result = growcam.start_video_recording(30, 7, camera_id=camera["camera_id"])
            for _ in range(100):
                if not growcam.status_snapshot(camera["camera_id"])["recording"]:
                    break
                time.sleep(0.01)
            recordings = growcam.list_recordings(camera_id=camera["camera_id"])
            require(
                result["success"]
                and recordings["total"] == 1
                and recordings["items"][0]["batch_id"] == 7
                and "-c:v" in command and "copy" in command
                and "+faststart" in command,
                "Originaler RTSP-Stream wird einem Durchgang zugeordnet und als MP4 gespeichert",
            )
            filename = recordings["items"][0]["filename"]
            require(
                growcam.resolve_recording(camera["camera_id"], 7, filename).is_file()
                and growcam.resolve_recording(camera["camera_id"], 7, "../recording.mp4") is None
                and growcam.delete_recording(camera["camera_id"], 7, filename)["success"],
                "Videoaufnahme kann sicher heruntergeladen und gelöscht werden",
            )
            require(
                not growcam.start_video_recording(29, 7, camera_id=camera["camera_id"])["success"]
                and not growcam.start_video_recording(601, 7, camera_id=camera["camera_id"])["success"],
                "Aufnahmedauer bleibt strikt zwischen 30 Sekunden und 10 Minuten",
            )
        finally:
            growcam.subprocess.run = original_run
            growcam.shutil.which = original_which
            (
                growcam.CONFIG_FILE, growcam.CAMERA_DIR,
                growcam.LATEST_IMAGE, growcam.TIMELAPSE_DIR,
            ) = original_paths
            with growcam._config_lock:
                growcam._configs = {item["camera_id"]: dict(item) for item in original_configs}
                growcam._config = original_config
                growcam._next_camera_number = original_next

    routes = (ROOT / "routes/camera.py").read_text(encoding="utf-8")
    service = (ROOT / "services/growcam.py").read_text(encoding="utf-8")
    nav = (ROOT / "templates/media/_nav.html").read_text(encoding="utf-8")
    camera_template = (ROOT / "templates/plants/camera.html").read_text(encoding="utf-8")
    timelapse_template = (ROOT / "templates/plants/timelapse.html").read_text(encoding="utf-8")
    photo_template = (ROOT / "templates/plants/photo_form.html").read_text(encoding="utf-8")
    plant_routes = (ROOT / "routes/plant_management.py").read_text(encoding="utf-8")
    explorer = (ROOT / "templates/plants/media_explorer.html").read_text(encoding="utf-8")
    require(
        "growcam_timelapse_page" in nav
        and "active_page = 'timelapse'" in timelapse_template
        and "growcam_timelapse_configure" in timelapse_template
        and "timelapse_enabled" not in camera_template,
        "Zeitraffer besitzt neben Kamera ein eigenes Modul mit eigenen Einstellungen",
    )
    require(
        "growcam_recording_start" in routes
        and 'name="duration_sec"' in camera_template
        and 'name="batch_id"' in camera_template
        and "growcam_recording_file" in explorer
        and "kind='recordings'" in explorer
        and "recording_dir_path" in service,
        "Videoaufnahme, Download, Löschung und Medien-Explorer sind vollständig verbunden",
    )
    require(
        'name="growcam_camera_id"' in photo_template
        and "growcam_capture_snapshot" in plant_routes
        and "growcam_latest_image_path" in plant_routes,
        "Pflanzenfoto kann direkt von einer ausgewählten GrowCam aufgenommen werden",
    )
    require(
        permission_requirement("/pflanzenmanagement/kamera/video-aufnahme", "POST").permissions
        == ("plants.edit",)
        and permission_requirement("/pflanzenmanagement/zeitraffer", "GET").permissions
        == ("plants.view",),
        "Neue Medienaktionen bleiben rollenbasiert geschützt",
    )
    print("✅ GrowCam-Aufnahme und Pflanzenfoto-Integration vollständig geprüft")


if __name__ == "__main__":
    main()
