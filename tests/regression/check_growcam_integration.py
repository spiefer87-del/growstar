#!/usr/bin/env python3
"""Regressionstest für die lokale VIVOSUN-GrowCam-C4-Anbindung."""

from pathlib import Path
import tempfile
import sys
import time


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
        growcam.CONFIG_FILE,
        growcam.CAMERA_DIR,
        growcam.LATEST_IMAGE,
        growcam.TIMELAPSE_DIR,
    )
    original_which = growcam.shutil.which
    original_run = growcam.subprocess.run
    original_popen = growcam.subprocess.Popen
    original_config = growcam.public_config()
    captured_command = []

    with tempfile.TemporaryDirectory(prefix="growstar-growcam-") as temp_dir:
        temp = Path(temp_dir)
        growcam.CONFIG_FILE = temp / "instance" / "growcam.json"
        growcam.CAMERA_DIR = temp / "instance" / "growcam"
        growcam.LATEST_IMAGE = growcam.CAMERA_DIR / "latest.jpg"
        growcam.TIMELAPSE_DIR = growcam.CAMERA_DIR / "timelapse"

        def fake_run(command, **kwargs):
            captured_command[:] = command
            if str(command[-1]).endswith(".jpg"):
                Image.effect_noise((320, 180), 70).convert("RGB").save(
                    command[-1], format="JPEG", quality=90
                )
            else:
                Path(command[-1]).write_bytes(b"test-mp4")

            class Result:
                returncode = 0
                stderr = ""

            require(
                kwargs.get("timeout") in (30, 600),
                "FFmpeg-Aufrufe besitzen feste Zeitlimits",
            )
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

            config = growcam.save_config({
                **config,
                "batch_id": 7,
                "timelapse_enabled": True,
                "timelapse_interval_sec": 300,
                "retention_days": 30,
                "video_retention_count": 25,
                "live_width": 2560,
                "live_fps": 15,
            })
            growcam.capture_snapshot(archive=True)
            growcam.capture_snapshot(archive=True)
            require(
                growcam.timelapse_summary(7)["frame_count"] == 2,
                "Automatische Aufnahmen werden getrennt nach Durchgang archiviert",
            )
            render = growcam.start_timelapse_render({
                "video_fps": 60,
                "video_width": 2560,
                "video_crf": 32,
            })
            for _ in range(100):
                if not growcam.status_snapshot()["timelapse_rendering"]:
                    break
                time.sleep(0.01)
            summary = growcam.timelapse_summary(7)
            require(
                render["success"] is True
                and summary["latest_video"]
                and "libx264" in captured_command
                and "+faststart" in captured_command,
                "Durchgangsaufnahmen werden als browserfähiges MP4 gerendert",
            )
            video_page = growcam.list_timelapse_videos(page=1, per_page=24)
            archive_page = growcam.list_all_timelapse_frames(page=1, per_page=24)
            storage = growcam.growcam_storage_summary()
            require(
                video_page["total"] == 1
                and video_page["items"][0]["batch_id"] == 7
                and archive_page["total"] == 2
                and archive_page["items"][0]["batch_id"] == 7
                and storage["video_count"] == 1
                and storage["frame_count"] == 2,
                "Medien-Explorer zählt Zeitrafferbilder und Videos über ihre Durchgangsordner",
            )
            require(
                "60" in captured_command
                and "scale=2560:-2:force_original_aspect_ratio=decrease,format=yuv420p"
                in captured_command
                and "32" in captured_command,
                "Bildrate, Auflösung und Kompression werden erst beim Video festgelegt",
            )

            frame_page = growcam.list_timelapse_frames(7, page=1, per_page=24)
            selected_frame = frame_page["items"][0]["filename"]
            thumbnail = growcam.resolve_timelapse_frame(
                7, selected_frame, thumbnail=True
            )
            require(
                frame_page["total"] == 2
                and thumbnail is not None
                and thumbnail.is_file()
                and growcam.resolve_timelapse_frame(7, "../latest.jpg") is None,
                "Bildarchiv bietet paginierte Vorschauen ohne unsichere Dateipfade",
            )
            deleted = growcam.delete_timelapse_frame(7, selected_frame)
            require(
                deleted["success"] is True
                and growcam.timelapse_summary(7)["frame_count"] == 1,
                "Einzelne ungeeignete Zeitrafferbilder können entfernt werden",
            )
            video_name = video_page["items"][0]["filename"]
            require(
                growcam.delete_timelapse_video(7, "../latest.mp4")["success"] is False
                and growcam.delete_timelapse_video(7, video_name)["success"] is True
                and growcam.list_timelapse_videos()["total"] == 0,
                "Zeitraffer-Videos lassen sich einzeln und ohne unsichere Dateipfade löschen",
            )

            jpeg = growcam.LATEST_IMAGE.read_bytes()

            class FakeStdout:
                def __init__(self):
                    self.chunks = [jpeg[:300], jpeg[300:], b""]

                def read(self, _size):
                    return self.chunks.pop(0)

            class FakeProcess:
                def __init__(self, command, **_kwargs):
                    captured_command[:] = command
                    self.stdout = FakeStdout()

                def poll(self):
                    return 0

            growcam.subprocess.Popen = FakeProcess
            stream = growcam.mjpeg_stream()
            first_frame = next(stream)
            stream.close()
            require(
                first_frame.startswith(b"--growcam\r\nContent-Type: image/jpeg")
                and "image2pipe" in captured_command
                and "mjpeg" in captured_command
                and "fps=15,scale=2560:-2" in captured_command,
                "HEVC-Stream wird bis 2560 Pixel und 15 FPS als MJPEG bereitgestellt",
            )

            read_requirement = permission_requirement(
                "/pflanzenmanagement/kamera", "GET"
            )
            write_requirement = permission_requirement(
                "/pflanzenmanagement/kamera/aufnahme", "POST"
            )
            stream_requirement = permission_requirement(
                "/pflanzenmanagement/kamera/live.mjpg", "GET"
            )
            viewer_requirement = permission_requirement(
                "/pflanzenmanagement/kamera/live", "GET"
            )
            media_requirement = permission_requirement(
                "/pflanzenmanagement/medien", "GET"
            )
            timelapse_requirement = permission_requirement(
                "/pflanzenmanagement/kamera/zeitraffer", "POST"
            )
            video_delete_requirement = permission_requirement(
                "/pflanzenmanagement/kamera/zeitraffer/7/timelapse-test.mp4/loeschen",
                "POST",
            )
            delete_requirement = permission_requirement(
                "/pflanzenmanagement/kamera/zeitraffer-bild/7/frame-test.jpg/loeschen",
                "POST",
            )
            api_requirement = permission_requirement(
                "/api/plant-management/camera/status", "GET"
            )
            require(
                read_requirement.permissions == ("plants.view",)
                and stream_requirement.permissions == ("plants.view",)
                and viewer_requirement.permissions == ("plants.view",)
                and media_requirement.permissions == ("plants.view",)
                and api_requirement.permissions == ("plants.view",)
                and write_requirement.permissions == ("plants.edit",)
                and timelapse_requirement.permissions == ("plants.edit",)
                and video_delete_requirement.permissions == ("plants.edit",)
                and delete_requirement.permissions == ("plants.edit",),
                "Kamerabild, Status und Bedienung sind rollenbasiert geschützt",
            )

            app_source = (ROOT / "app.py").read_text(encoding="utf-8")
            template = (ROOT / "templates/plants/camera.html").read_text(encoding="utf-8")
            live_template = (ROOT / "templates/plants/camera_live.html").read_text(
                encoding="utf-8"
            )
            station_template = (ROOT / "templates/grow_control.html").read_text(
                encoding="utf-8"
            )
            media_template = (ROOT / "templates/plants/media_explorer.html").read_text(
                encoding="utf-8"
            )
            base_template = (ROOT / "templates/base.html").read_text(encoding="utf-8")
            plant_nav = (ROOT / "templates/plants/_nav.html").read_text(
                encoding="utf-8"
            )
            media_nav = (ROOT / "templates/media/_nav.html").read_text(
                encoding="utf-8"
            )
            dashboard_template = (ROOT / "templates/dashboard.html").read_text(
                encoding="utf-8"
            )
            dashboard_routes = (ROOT / "routes/dashboard.py").read_text(
                encoding="utf-8"
            )
            require(
                "register_camera_routes(app)" in app_source
                and '"growstar-growcam"' in app_source
                and "growcam_live" in template
                and "growcam_timelapse_create" in template
                and 'name="video_fps"' in template
                and 'name="timelapse_fps"' not in template
                and "2560 px · Kamera-Maximum" in template
                and 'timelapse_frames["items"]' in template
                and "timelapse_frames.items" not in template,
                "Route, Hintergrundaufnahme und Kameraansicht sind vollständig eingebunden",
            )
            require(
                'name="video_retention_count"' in template
                and "Video herunterladen" in template
                and "plant_media_explorer" in template
                and "growcam_timelapse_video_delete" in media_template
                and "growcam_timelapse_frame_delete" in media_template
                and "timelapse_frames" in media_template
                and "download=1" in media_template
                and "instance/growcam/" in media_template,
                "Video-Aufbewahrung, Download und zentraler Medien-Explorer sind eingebunden",
            )
            require(
                "plant_media_explorer" in base_template
                and "Dateien & Speicher" in base_template
                and "growstar_media_active" in base_template
                and "Fotos, Videos & Kamera" in base_template
                and "plant_media_explorer" not in plant_nav
                and "growcam_page" not in plant_nav
                and "plant_media_explorer" in media_nav
                and "growcam_page" in media_nav
                and '{% include "media/_nav.html" %}' in template
                and "<h2>Medien</h2>" in dashboard_template
                and "timelapse_frames" in media_template
                and "growcam_timelapse_frame_delete" in media_template,
                "Medien ist als eigenes Modul mit Explorer, Foto-Manager und Kamera verankert",
            )
            require(
                "growcam_live_viewer" in station_template
                and "station_camera_available" in station_template
                and "growcam_public_config" in dashboard_routes
                and 'camera.get("tent_id") == tent_id' in dashboard_routes
                and "requestFullscreen" in live_template
                and "growcam_live" in live_template
                and "grow_control_tent" in live_template,
                "Stationskamera öffnet ausschließlich an ihrer Station den bildschirmfüllenden Liveviewer",
            )
        finally:
            growcam.shutil.which = original_which
            growcam.subprocess.run = original_run
            growcam.subprocess.Popen = original_popen
            (
                growcam.CONFIG_FILE,
                growcam.CAMERA_DIR,
                growcam.LATEST_IMAGE,
                growcam.TIMELAPSE_DIR,
            ) = original_paths
            with growcam._config_lock:
                growcam._config = original_config

    print("✅ VIVOSUN GrowCam C4 Integration vollständig erfolgreich")


if __name__ == "__main__":
    main()
