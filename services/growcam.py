"""Lokaler Snapshot-Dienst für die VIVOSUN GrowCam C4 (VSC-GCC4)."""

from __future__ import annotations

import ipaddress
from datetime import date
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from urllib.parse import quote
import re


ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "instance" / "growcam.json"
CAMERA_DIR = ROOT / "instance" / "growcam"
LATEST_IMAGE = CAMERA_DIR / "latest.jpg"
TIMELAPSE_DIR = CAMERA_DIR / "timelapse"
PRIMARY_CAMERA_ID = "camera_1"
_CAMERA_ID_RE = re.compile(r"^camera_[1-9][0-9]*$")

DEFAULT_CONFIG = {
    "enabled": False,
    "name": "VIVOSUN GrowCam C4",
    "host": "",
    "port": 554,
    "path": "/live/ch00_0",
    "username": "admin",
    "interval_sec": 60,
    "tent_id": "tent_1",
    "batch_id": None,
    "timelapse_enabled": False,
    "timelapse_interval_sec": 900,
    "retention_days": 30,
    "video_retention_count": 25,
    "live_width": 2560,
    "live_fps": 15,
}

_config_lock = threading.RLock()
_capture_lock = threading.Lock()
_config = dict(DEFAULT_CONFIG)
_status = {
    "capturing": False,
    "last_capture": None,
    "last_error": None,
    "last_duration_ms": None,
    "width": None,
    "height": None,
    "last_archived": None,
    "live_clients": 0,
    "live_error": None,
    "timelapse_rendering": False,
    "timelapse_error": None,
    "timelapse_progress": 0,
    "timelapse_stage": "Bereit",
    "timelapse_processed_frames": 0,
    "timelapse_total_frames": 0,
    "timelapse_started_at": None,
    "timelapse_finished_at": None,
    "last_video": None,
    "render_options": None,
    "recording": False,
    "recording_error": None,
    "recording_started_at": None,
    "recording_duration_sec": None,
    "last_recording": None,
}
_timelapse_lock = threading.Lock()
_configs = {}
_statuses = {PRIMARY_CAMERA_ID: _status}
_capture_locks = {PRIMARY_CAMERA_ID: _capture_lock}
_timelapse_locks = {PRIMARY_CAMERA_ID: _timelapse_lock}
_recording_locks = {PRIMARY_CAMERA_ID: threading.Lock()}
_next_camera_number = 2


def _normalize_camera_id(value):
    camera_id = str(value or "").strip().lower()
    if not _CAMERA_ID_RE.fullmatch(camera_id):
        raise ValueError("Die Kamera-ID ist ungültig.")
    return camera_id


def _new_status():
    return {
        "capturing": False,
        "last_capture": None,
        "last_error": None,
        "last_duration_ms": None,
        "width": None,
        "height": None,
        "last_archived": None,
        "live_clients": 0,
        "live_error": None,
        "timelapse_rendering": False,
        "timelapse_error": None,
        "timelapse_progress": 0,
        "timelapse_stage": "Bereit",
        "timelapse_processed_frames": 0,
        "timelapse_total_frames": 0,
        "timelapse_started_at": None,
        "timelapse_finished_at": None,
        "last_video": None,
        "render_options": None,
        "recording": False,
        "recording_error": None,
        "recording_started_at": None,
        "recording_duration_sec": None,
        "last_recording": None,
    }


def _status_for(camera_id):
    camera_id = _normalize_camera_id(camera_id)
    with _config_lock:
        return _statuses.setdefault(camera_id, _new_status())


def _capture_lock_for(camera_id):
    camera_id = _normalize_camera_id(camera_id)
    with _config_lock:
        return _capture_locks.setdefault(camera_id, threading.Lock())


def _timelapse_lock_for(camera_id):
    camera_id = _normalize_camera_id(camera_id)
    with _config_lock:
        return _timelapse_locks.setdefault(camera_id, threading.Lock())


def _recording_lock_for(camera_id):
    camera_id = _normalize_camera_id(camera_id)
    with _config_lock:
        return _recording_locks.setdefault(camera_id, threading.Lock())


def _camera_dir(camera_id):
    camera_id = _normalize_camera_id(camera_id)
    # Die erste Kamera behält absichtlich den bisherigen Ordner. Damit bleiben
    # vorhandene Standbilder, Archive und Videos nach der Migration sichtbar.
    return CAMERA_DIR if camera_id == PRIMARY_CAMERA_ID else CAMERA_DIR / camera_id


def latest_image_path(camera_id=PRIMARY_CAMERA_ID):
    return LATEST_IMAGE if camera_id == PRIMARY_CAMERA_ID else _camera_dir(camera_id) / "latest.jpg"


def timelapse_dir_path(camera_id=PRIMARY_CAMERA_ID):
    return TIMELAPSE_DIR if camera_id == PRIMARY_CAMERA_ID else _camera_dir(camera_id) / "timelapse"


def recording_dir_path(camera_id=PRIMARY_CAMERA_ID):
    return _camera_dir(camera_id) / "recordings"


def _atomic_write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=".growcam-",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _normalize_config(data, camera_id=PRIMARY_CAMERA_ID):
    data = dict(data or {})
    result = dict(DEFAULT_CONFIG)
    result["camera_id"] = _normalize_camera_id(
        data.get("camera_id") or camera_id
    )
    result["enabled"] = bool(data.get("enabled", False))
    result["name"] = str(data.get("name") or DEFAULT_CONFIG["name"]).strip()[:80]

    host = str(data.get("host") or "").strip()
    if host:
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError("Die Kamera-IP ist ungültig.") from exc
        if address.version != 4 or not (address.is_private or address.is_link_local):
            raise ValueError("Die GrowCam muss eine lokale IPv4-Adresse verwenden.")
        host = str(address)
    result["host"] = host

    try:
        port = int(data.get("port", DEFAULT_CONFIG["port"]))
    except (TypeError, ValueError) as exc:
        raise ValueError("Der RTSP-Port ist ungültig.") from exc
    if not 1 <= port <= 65535:
        raise ValueError("Der RTSP-Port muss zwischen 1 und 65535 liegen.")
    result["port"] = port

    path = str(data.get("path") or DEFAULT_CONFIG["path"]).strip()
    if not path.startswith("/") or any(ord(char) < 32 for char in path):
        raise ValueError("Der RTSP-Pfad muss mit '/' beginnen.")
    if len(path) > 160:
        raise ValueError("Der RTSP-Pfad ist zu lang.")
    result["path"] = path

    username = str(data.get("username") or DEFAULT_CONFIG["username"]).strip()
    if not username or len(username) > 80:
        raise ValueError("Der RTSP-Benutzer ist ungültig.")
    result["username"] = username

    try:
        interval = int(data.get("interval_sec", DEFAULT_CONFIG["interval_sec"]))
    except (TypeError, ValueError) as exc:
        raise ValueError("Das Aufnahmeintervall ist ungültig.") from exc
    result["interval_sec"] = max(15, min(interval, 3600))

    tent_id = str(data.get("tent_id") or DEFAULT_CONFIG["tent_id"]).strip()
    if not tent_id or len(tent_id) > 64:
        raise ValueError("Die Stations-ID ist ungültig.")
    result["tent_id"] = tent_id

    raw_batch_id = data.get("batch_id")
    if raw_batch_id in (None, ""):
        result["batch_id"] = None
    else:
        try:
            batch_id = int(raw_batch_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Der ausgewählte Durchgang ist ungültig.") from exc
        if batch_id < 1:
            raise ValueError("Der ausgewählte Durchgang ist ungültig.")
        result["batch_id"] = batch_id

    result["timelapse_enabled"] = bool(data.get("timelapse_enabled", False))
    if result["timelapse_enabled"] and result["batch_id"] is None:
        raise ValueError("Für den Zeitraffer muss ein Durchgang ausgewählt sein.")

    for key, minimum, maximum in (
        ("timelapse_interval_sec", 60, 86400),
        ("retention_days", 1, 365),
        ("live_width", 480, 2560),
        ("live_fps", 1, 15),
    ):
        try:
            value = int(data.get(key, DEFAULT_CONFIG[key]))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Der Wert für {key} ist ungültig.") from exc
        result[key] = max(minimum, min(value, maximum))

    raw_video_retention = data.get("video_retention_count")
    if raw_video_retention in (None, ""):
        raw_video_retention = DEFAULT_CONFIG["video_retention_count"]
    try:
        video_retention_count = int(raw_video_retention)
    except (TypeError, ValueError) as exc:
        raise ValueError("Die Video-Aufbewahrung ist ungültig.") from exc
    if video_retention_count not in {0, 5, 10, 25, 50, 100}:
        raise ValueError("Die Video-Aufbewahrung ist ungültig.")
    result["video_retention_count"] = video_retention_count

    if result["enabled"] and not result["host"]:
        raise ValueError("Vor dem Aktivieren muss eine Kamera-IP eingetragen sein.")
    return result


def load_config():
    global _config, _configs, _next_camera_number
    with _config_lock:
        data = {}
        if CONFIG_FILE.is_file():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception as exc:
                print("⚠️ GrowCam-Konfiguration konnte nicht gelesen werden:", exc)
        try:
            if isinstance(data, dict) and isinstance(data.get("cameras"), list):
                loaded = {}
                for item in data["cameras"]:
                    normalized = _normalize_config(
                        item,
                        item.get("camera_id") if isinstance(item, dict) else None,
                    )
                    loaded[normalized["camera_id"]] = normalized
                _configs = loaded
                highest = max(
                    (int(key.split("_", 1)[1]) for key in loaded),
                    default=0,
                )
                _next_camera_number = max(
                    highest + 1,
                    int(data.get("next_camera_number") or 1),
                )
            else:
                # Format 1 enthielt genau eine Kamera. Sie bleibt camera_1 und
                # verwendet weiter den historischen Medienordner.
                legacy = _normalize_config(data, PRIMARY_CAMERA_ID)
                _configs = {PRIMARY_CAMERA_ID: legacy}
                _next_camera_number = 2
            if not _configs:
                empty = _normalize_config({}, PRIMARY_CAMERA_ID)
                _configs = {PRIMARY_CAMERA_ID: empty}
            _config = dict(_configs.get(PRIMARY_CAMERA_ID) or next(iter(_configs.values())))
        except (TypeError, ValueError) as exc:
            print("⚠️ GrowCam-Konfiguration ist ungültig:", exc)
            _config = _normalize_config({}, PRIMARY_CAMERA_ID)
            _configs = {PRIMARY_CAMERA_ID: dict(_config)}
            _next_camera_number = 2
        return dict(_config)


def _save_registry():
    _atomic_write_json(CONFIG_FILE, {
        "version": 2,
        "next_camera_number": _next_camera_number,
        "cameras": [dict(_configs[key]) for key in sorted(_configs)],
    })


def save_config(data, camera_id=None):
    global _config
    requested_id = camera_id or dict(data or {}).get("camera_id") or PRIMARY_CAMERA_ID
    normalized = _normalize_config(data, requested_id)
    with _config_lock:
        _configs[normalized["camera_id"]] = normalized
        _save_registry()
        if normalized["camera_id"] == PRIMARY_CAMERA_ID or not _config:
            _config = dict(normalized)
    return public_config(normalized["camera_id"])


def public_config(camera_id=None):
    with _config_lock:
        if camera_id is None:
            camera_id = PRIMARY_CAMERA_ID if PRIMARY_CAMERA_ID in _configs else next(iter(_configs), None)
        if camera_id is None:
            return _normalize_config({}, PRIMARY_CAMERA_ID)
        try:
            camera_id = _normalize_camera_id(camera_id)
        except ValueError:
            return None
        config = _configs.get(camera_id)
        return dict(config) if config else None


def list_public_configs():
    with _config_lock:
        return [dict(_configs[key]) for key in sorted(_configs)]


def create_camera(data):
    global _config, _next_camera_number
    with _config_lock:
        number = max(1, int(_next_camera_number))
        while f"camera_{number}" in _configs:
            number += 1
        camera_id = f"camera_{number}"
        _next_camera_number = number + 1
        normalized = _normalize_config({**dict(data or {}), "camera_id": camera_id}, camera_id)
        _configs[camera_id] = normalized
        _save_registry()
        if not _config:
            _config = dict(normalized)
    return dict(normalized)


def camera_for_tent(tent_id, *, enabled_only=True):
    tent_id = str(tent_id or "")
    for camera in list_public_configs():
        if camera.get("tent_id") != tent_id:
            continue
        if enabled_only and (not camera.get("enabled") or not camera.get("host")):
            continue
        return camera
    return None


def _rtsp_url(config):
    user = quote(str(config.get("username") or "admin"), safe="")
    host = config["host"]
    port = int(config["port"])
    path = config["path"]
    # Die bestätigte GrowCam-C4-Firmware akzeptiert Benutzer admin mit leerem
    # Kennwort. Es werden deshalb keine Cloud- oder App-Zugangsdaten gespeichert.
    return f"rtsp://{user}:@{host}:{port}{path}"


def _image_dimensions(path):
    try:
        from PIL import Image
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            return int(image.width), int(image.height)
    except Exception as exc:
        raise RuntimeError("FFmpeg erzeugte kein gültiges JPEG-Bild.") from exc


def _safe_error(stderr, rtsp_url):
    text = str(stderr or "").strip().replace(rtsp_url, "rtsp://growcam")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return (lines[-1] if lines else "GrowCam-Aufnahme fehlgeschlagen")[:300]


def _batch_dir(batch_id, camera_id=PRIMARY_CAMERA_ID):
    return timelapse_dir_path(camera_id) / f"batch_{int(batch_id)}"


def _thumbnail_dir(batch_id, camera_id=PRIMARY_CAMERA_ID):
    return _batch_dir(batch_id, camera_id) / "thumbnails"


def _safe_media_name(filename, *, prefix, suffix):
    name = str(filename or "")
    if not name.startswith(prefix) or not name.endswith(suffix):
        return None
    if any(
        char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
        for char in name
    ):
        return None
    return name


def _create_thumbnail(source, target):
    from PIL import Image

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=".growcam-thumb-",
        suffix=".jpg",
        dir=str(target.parent),
    )
    os.close(fd)
    try:
        with Image.open(source) as image:
            image = image.convert("RGB")
            image.thumbnail((480, 270))
            image.save(temp_name, format="JPEG", quality=78, optimize=True)
        os.chmod(temp_name, 0o640)
        os.replace(temp_name, target)
    finally:
        try:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        except OSError:
            pass


def _archive_latest(config, captured_at):
    camera_id = config["camera_id"]
    batch_id = config.get("batch_id")
    if not config.get("timelapse_enabled") or not batch_id:
        return None
    directory = _batch_dir(batch_id, camera_id)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(captured_at))
    target = directory / f"frame-{stamp}-{time.time_ns() % 1_000_000:06d}.jpg"
    shutil.copy2(latest_image_path(camera_id), target)
    os.chmod(target, 0o640)
    _create_thumbnail(target, _thumbnail_dir(batch_id, camera_id) / target.name)

    cutoff = captured_at - int(config.get("retention_days") or 120) * 86400
    for old_frame in directory.glob("frame-*.jpg"):
        try:
            if old_frame.stat().st_mtime < cutoff:
                old_frame.unlink()
                thumbnail = _thumbnail_dir(batch_id, camera_id) / old_frame.name
                if thumbnail.is_file():
                    thumbnail.unlink()
        except OSError:
            pass
    return target


def capture_snapshot(*, archive=False, camera_id=None):
    config = public_config(camera_id)
    if config is None:
        return {"success": False, "error": "GrowCam wurde nicht gefunden."}
    camera_id = config["camera_id"]
    capture_lock = _capture_lock_for(camera_id)
    status = _status_for(camera_id)
    if not config.get("enabled"):
        return {"success": False, "error": "GrowCam ist nicht aktiviert."}
    if not config.get("host"):
        return {"success": False, "error": "GrowCam-IP fehlt."}
    if not capture_lock.acquire(blocking=False):
        return {"success": False, "error": "Eine GrowCam-Aufnahme läuft bereits."}

    started = time.monotonic()
    temp_name = None
    with _config_lock:
        status["capturing"] = True
    try:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("FFmpeg ist nicht installiert.")

        camera_dir = _camera_dir(camera_id)
        camera_dir.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=".growcam-frame-",
            suffix=".jpg",
            dir=str(camera_dir),
        )
        os.close(fd)
        rtsp_url = _rtsp_url(config)
        process = subprocess.run(
            [
                ffmpeg,
                "-nostdin",
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-rtsp_transport", "tcp",
                "-i", rtsp_url,
                "-frames:v", "1",
                "-q:v", "3",
                temp_name,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(_safe_error(process.stderr, rtsp_url))
        if not os.path.isfile(temp_name) or os.path.getsize(temp_name) < 1024:
            raise RuntimeError("GrowCam lieferte kein vollständiges Bild.")

        width, height = _image_dimensions(temp_name)
        os.chmod(temp_name, 0o640)
        os.replace(temp_name, latest_image_path(camera_id))
        temp_name = None
        captured_at = time.time()
        archived = _archive_latest(config, captured_at) if archive else None
        with _config_lock:
            status.update({
                "capturing": False,
                "last_capture": captured_at,
                "last_error": None,
                "last_duration_ms": round((time.monotonic() - started) * 1000),
                "width": width,
                "height": height,
                "last_archived": captured_at if archived else status.get("last_archived"),
            })
        return {"success": True, **status_snapshot(camera_id)}
    except subprocess.TimeoutExpired:
        error = "GrowCam-Aufnahme hat nach 30 Sekunden nicht geantwortet."
    except Exception as exc:
        error = str(exc).strip() or type(exc).__name__
    finally:
        if temp_name:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
        with _config_lock:
            status["capturing"] = False
        capture_lock.release()

    with _config_lock:
        status["last_error"] = error[:300]
    return {"success": False, "error": error, **status_snapshot(camera_id)}


def status_snapshot(camera_id=None):
    config = public_config(camera_id)
    if config is None:
        return {"configured": False, "enabled": False, "error": "GrowCam wurde nicht gefunden."}
    camera_id = config["camera_id"]
    status_ref = _status_for(camera_id)
    latest_image = latest_image_path(camera_id)
    with _config_lock:
        status = dict(status_ref)
    image_exists = latest_image.is_file()
    if image_exists and not status.get("last_capture"):
        status["last_capture"] = latest_image.stat().st_mtime
    batch_id = config.get("batch_id")
    archive = timelapse_summary(batch_id, camera_id=camera_id)
    return {
        **status,
        "enabled": bool(config.get("enabled")),
        "configured": bool(config.get("host")),
        "name": config.get("name"),
        "camera_id": camera_id,
        "tent_id": config.get("tent_id"),
        "interval_sec": config.get("interval_sec"),
        "batch_id": batch_id,
        "timelapse_enabled": bool(config.get("timelapse_enabled")),
        "timelapse_interval_sec": config.get("timelapse_interval_sec"),
        "retention_days": config.get("retention_days"),
        "video_retention_count": config.get("video_retention_count"),
        "live_width": config.get("live_width"),
        "live_fps": config.get("live_fps"),
        "timelapse": archive,
        "image_available": image_exists,
        "image_version": int(latest_image.stat().st_mtime) if image_exists else None,
    }


def _video_files(batch_id, camera_id=PRIMARY_CAMERA_ID):
    if not batch_id:
        return []
    return sorted(_batch_dir(batch_id, camera_id).glob("timelapse-*.mp4"), reverse=True)


def timelapse_summary(batch_id=None, *, camera_id=PRIMARY_CAMERA_ID):
    try:
        directory = _batch_dir(batch_id, camera_id) if batch_id else None
        frames = list(directory.glob("frame-*.jpg")) if directory and directory.is_dir() else []
        videos = _video_files(batch_id, camera_id)
    except (OSError, TypeError, ValueError):
        frames, videos = [], []
    latest_video = videos[0] if videos else None
    return {
        "frame_count": len(frames),
        "latest_video": latest_video.name if latest_video else None,
        "latest_video_mtime": latest_video.stat().st_mtime if latest_video else None,
    }


def resolve_timelapse_video(batch_id, filename, *, camera_id=PRIMARY_CAMERA_ID):
    name = _safe_media_name(filename, prefix="timelapse-", suffix=".mp4")
    if name is None:
        return None
    candidate = _batch_dir(batch_id, camera_id) / name
    return candidate if candidate.is_file() else None


def list_timelapse_videos(batch_id=None, *, camera_id=None, page=1, per_page=24):
    """Listet erzeugte Videos sicher über alle oder genau einen Durchgang."""

    candidates = []
    try:
        camera_ids = [camera_id] if camera_id else [item["camera_id"] for item in list_public_configs()]
        for current_camera_id in camera_ids:
            if batch_id:
                directories = [_batch_dir(batch_id, current_camera_id)]
            else:
                base = timelapse_dir_path(current_camera_id)
                directories = [
                    path for path in base.glob("batch_*")
                    if path.is_dir() and path.name[6:].isdigit()
                ]
            for directory in directories:
                directory_batch_id = int(directory.name[6:])
                for video in directory.glob("timelapse-*.mp4"):
                    try:
                        stat = video.stat()
                    except OSError:
                        continue
                    candidates.append({
                        "camera_id": current_camera_id,
                        "batch_id": directory_batch_id,
                        "filename": video.name,
                        "created_at": stat.st_mtime,
                        "size_bytes": stat.st_size,
                    })
    except (OSError, TypeError, ValueError):
        candidates = []

    candidates.sort(key=lambda item: item["created_at"], reverse=True)
    per_page = max(6, min(int(per_page), 100))
    pages = (len(candidates) + per_page - 1) // per_page
    page = max(1, min(int(page), pages or 1))
    start = (page - 1) * per_page
    return {
        "items": candidates[start:start + per_page],
        "page": page,
        "pages": pages,
        "total": len(candidates),
    }


def delete_timelapse_video(batch_id, filename, *, camera_id=PRIMARY_CAMERA_ID):
    if _timelapse_lock_for(camera_id).locked():
        return {
            "success": False,
            "error": "Während der Videoerstellung können keine Videos gelöscht werden.",
        }
    video = resolve_timelapse_video(batch_id, filename, camera_id=camera_id)
    if video is None:
        return {"success": False, "error": "Zeitraffer-Video wurde nicht gefunden."}
    try:
        video.unlink()
    except OSError as exc:
        return {
            "success": False,
            "error": f"Zeitraffer-Video konnte nicht gelöscht werden: {exc}",
        }
    return {"success": True, "filename": video.name}


def growcam_storage_summary():
    """Ermittelt die tatsächlich belegten GrowCam-Dateien ohne Dateiinhalte zu lesen."""

    totals = {
        "latest_count": 0,
        "latest_bytes": 0,
        "frame_count": 0,
        "frame_bytes": 0,
        "thumbnail_count": 0,
        "thumbnail_bytes": 0,
        "video_count": 0,
        "video_bytes": 0,
        "recording_count": 0,
        "recording_bytes": 0,
    }
    for camera in list_public_configs():
        latest_image = latest_image_path(camera["camera_id"])
        if latest_image.is_file():
            try:
                totals["latest_count"] += 1
                totals["latest_bytes"] += latest_image.stat().st_size
            except OSError:
                pass
    try:
        seen = set()
        files = []
        for camera in list_public_configs():
            directory = timelapse_dir_path(camera["camera_id"])
            if directory.is_dir() and directory not in seen:
                seen.add(directory)
                files.extend(directory.rglob("*"))
        for path in files:
            if not path.is_file():
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if path.name.startswith("frame-") and path.suffix.lower() == ".jpg":
                if path.parent.name == "thumbnails":
                    totals["thumbnail_count"] += 1
                    totals["thumbnail_bytes"] += size
                else:
                    totals["frame_count"] += 1
                    totals["frame_bytes"] += size
            elif path.name.startswith("timelapse-") and path.suffix.lower() == ".mp4":
                totals["video_count"] += 1
                totals["video_bytes"] += size
    except OSError:
        pass
    for camera in list_public_configs():
        try:
            for path in _recording_files(camera["camera_id"]):
                totals["recording_count"] += 1
                totals["recording_bytes"] += path.stat().st_size
        except OSError:
            pass
    totals["total_bytes"] = sum(
        totals[key]
        for key in (
            "latest_bytes", "frame_bytes", "thumbnail_bytes",
            "video_bytes", "recording_bytes",
        )
    )
    return totals


def list_timelapse_frames(batch_id, *, camera_id=PRIMARY_CAMERA_ID, page=1, per_page=24):
    if not batch_id:
        return {"items": [], "page": 1, "pages": 0, "total": 0}
    try:
        frames = sorted(_batch_dir(batch_id, camera_id).glob("frame-*.jpg"), reverse=True)
    except (OSError, TypeError, ValueError):
        frames = []
    per_page = max(6, min(int(per_page), 60))
    pages = (len(frames) + per_page - 1) // per_page
    page = max(1, min(int(page), pages or 1))
    start = (page - 1) * per_page
    items = []
    for frame in frames[start:start + per_page]:
        try:
            stat = frame.stat()
        except OSError:
            continue
        items.append({
            "filename": frame.name,
            "captured_at": stat.st_mtime,
            "size_bytes": stat.st_size,
        })
    return {"items": items, "page": page, "pages": pages, "total": len(frames)}


def timelapse_frame_days(batch_id, *, camera_id=PRIMARY_CAMERA_ID):
    """Counts available images by the Raspberry Pi's local calendar day."""
    days = {}
    if not batch_id:
        return days
    for frame in _batch_dir(batch_id, camera_id).glob("frame-*.jpg"):
        try:
            day = time.strftime("%Y-%m-%d", time.localtime(frame.stat().st_mtime))
        except OSError:
            continue
        days[day] = days.get(day, 0) + 1
    return days


def list_all_timelapse_frames(*, camera_id=None, page=1, per_page=24):
    """Listet Zeitrafferbilder aller Durchgänge für die zentrale Medienansicht."""

    candidates = []
    try:
        camera_ids = [camera_id] if camera_id else [item["camera_id"] for item in list_public_configs()]
        for current_camera_id in camera_ids:
            base = timelapse_dir_path(current_camera_id)
            directories = [
                path for path in base.glob("batch_*")
                if path.is_dir() and path.name[6:].isdigit()
            ]
            for directory in directories:
                directory_batch_id = int(directory.name[6:])
                for frame in directory.glob("frame-*.jpg"):
                    try:
                        stat = frame.stat()
                    except OSError:
                        continue
                    candidates.append({
                        "camera_id": current_camera_id,
                        "batch_id": directory_batch_id,
                        "filename": frame.name,
                        "captured_at": stat.st_mtime,
                        "size_bytes": stat.st_size,
                    })
    except OSError:
        candidates = []
    candidates.sort(key=lambda item: item["captured_at"], reverse=True)
    per_page = max(6, min(int(per_page), 100))
    pages = (len(candidates) + per_page - 1) // per_page
    page = max(1, min(int(page), pages or 1))
    start = (page - 1) * per_page
    return {
        "items": candidates[start:start + per_page],
        "page": page,
        "pages": pages,
        "total": len(candidates),
    }


def resolve_timelapse_frame(batch_id, filename, *, camera_id=PRIMARY_CAMERA_ID, thumbnail=False):
    name = _safe_media_name(filename, prefix="frame-", suffix=".jpg")
    if name is None:
        return None
    source = _batch_dir(batch_id, camera_id) / name
    if not source.is_file():
        return None
    if not thumbnail:
        return source
    target = _thumbnail_dir(batch_id, camera_id) / name
    if not target.is_file():
        try:
            _create_thumbnail(source, target)
        except Exception:
            return source
    return target


def delete_timelapse_frame(batch_id, filename, *, camera_id=PRIMARY_CAMERA_ID):
    if _timelapse_lock_for(camera_id).locked():
        return {"success": False, "error": "Während der Videoerstellung können keine Bilder gelöscht werden."}
    frame = resolve_timelapse_frame(batch_id, filename, camera_id=camera_id)
    if frame is None:
        return {"success": False, "error": "Zeitrafferbild wurde nicht gefunden."}
    thumbnail = _thumbnail_dir(batch_id, camera_id) / frame.name
    try:
        frame.unlink()
        if thumbnail.is_file():
            thumbnail.unlink()
    except OSError as exc:
        return {"success": False, "error": f"Zeitrafferbild konnte nicht gelöscht werden: {exc}"}
    return {"success": True, "filename": frame.name}


def _normalize_render_options(data):
    data = dict(data or {})
    try:
        fps = int(data.get("video_fps", 15))
        width = int(data.get("video_width", 1920))
        crf = int(data.get("video_crf", 23))
    except (TypeError, ValueError) as exc:
        raise ValueError("Die Videoeinstellungen sind ungültig.") from exc
    if fps not in {5, 10, 15, 20, 25, 30, 50, 60}:
        raise ValueError("Die Zeitraffer-Bildrate ist ungültig.")
    if width not in {960, 1280, 1920, 2560}:
        raise ValueError("Die Videoauflösung ist ungültig.")
    if crf not in {18, 21, 23, 26, 28, 32}:
        raise ValueError("Die Videokompression ist ungültig.")
    return {"video_fps": fps, "video_width": width, "video_crf": crf}


def _update_timelapse_progress(status, frame_count, processed_frames):
    processed = max(0, min(int(processed_frames or 0), int(frame_count or 0)))
    percent = 5
    if frame_count:
        percent = min(95, 5 + round((processed / frame_count) * 90))
    with _config_lock:
        status["timelapse_progress"] = max(
            int(status.get("timelapse_progress") or 0), percent
        )
        status["timelapse_stage"] = "Video wird kodiert"
        status["timelapse_processed_frames"] = processed


def _monitor_timelapse_progress(progress_file, status, frame_count, stop_event):
    """Liest die von FFmpeg geschriebenen Framewerte während des Renderns."""
    last_processed = -1
    while not stop_event.wait(0.25):
        try:
            content = progress_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        matches = re.findall(r"(?m)^frame=(\d+)\s*$", content)
        if not matches:
            continue
        processed = int(matches[-1])
        if processed != last_processed:
            _update_timelapse_progress(status, frame_count, processed)
            last_processed = processed


def _render_timelapse_worker(config, options, selected_frames):
    camera_id = config["camera_id"]
    status = _status_for(camera_id)
    render_lock = _timelapse_lock_for(camera_id)
    batch_id = config["batch_id"]
    directory = _batch_dir(batch_id, camera_id)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    output = directory / f"timelapse-{stamp}.mp4"
    temp_output = directory / f".timelapse-{stamp}.mp4"
    progress_file = directory / f".timelapse-{stamp}.progress"
    progress_stop = threading.Event()
    frame_count = len(selected_frames)
    try:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("FFmpeg ist nicht installiert.")
        # Freeze the exact selection without duplicating the image data. This also
        # prevents a newly archived image from joining an already running render.
        selection = tempfile.TemporaryDirectory(prefix=".timelapse-selection-", dir=directory)
        try:
            for frame in selected_frames:
                os.link(frame, Path(selection.name) / frame.name)
            _encode_timelapse(ffmpeg, selection.name, options, progress_file, temp_output, status, frame_count, camera_id, progress_stop)
        finally:
            selection.cleanup()
        if not temp_output.is_file():
            raise RuntimeError("Das Zeitraffer-Video wurde nicht erstellt.")
        _update_timelapse_progress(status, frame_count, frame_count)
        with _config_lock:
            status["timelapse_progress"] = 97
            status["timelapse_stage"] = "Video wird abgeschlossen"
        os.chmod(temp_output, 0o640)
        os.replace(temp_output, output)
        retention_count = int(config.get("video_retention_count") or 0)
        if retention_count:
            for old_video in _video_files(batch_id, camera_id)[retention_count:]:
                try:
                    old_video.unlink()
                except OSError:
                    pass
        with _config_lock:
            status["last_video"] = output.name
            status["timelapse_error"] = None
            status["timelapse_progress"] = 100
            status["timelapse_stage"] = "Fertig"
            status["timelapse_processed_frames"] = frame_count
            status["timelapse_finished_at"] = time.time()
    except subprocess.TimeoutExpired:
        with _config_lock:
            status["timelapse_error"] = "Zeitraffer-Erstellung hat nach zehn Minuten nicht geantwortet."
            status["timelapse_stage"] = "Fehlgeschlagen"
            status["timelapse_finished_at"] = time.time()
    except Exception as exc:
        with _config_lock:
            status["timelapse_error"] = str(exc).strip() or type(exc).__name__
            status["timelapse_stage"] = "Fehlgeschlagen"
            status["timelapse_finished_at"] = time.time()
    finally:
        progress_stop.set()
        try:
            if temp_output.is_file():
                temp_output.unlink()
        except OSError:
            pass
        try:
            if progress_file.is_file():
                progress_file.unlink()
        except OSError:
            pass
        with _config_lock:
            status["timelapse_rendering"] = False
            status["render_options"] = None
        render_lock.release()


def _encode_timelapse(ffmpeg, selection_dir, options, progress_file, temp_output, status, frame_count, camera_id, progress_stop):
    with _config_lock:
        status["timelapse_progress"] = 5
        status["timelapse_stage"] = "Video wird kodiert"
    progress_thread = threading.Thread(
        target=_monitor_timelapse_progress,
        args=(progress_file, status, frame_count, progress_stop),
        name=f"growstar-growcam-timelapse-progress-{camera_id}",
        daemon=True,
    )
    progress_thread.start()
    try:
        process = subprocess.run(
            [
                ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-progress", str(progress_file), "-nostats",
                "-framerate", str(options["video_fps"]),
                "-pattern_type", "glob", "-i", str(Path(selection_dir) / "frame-*.jpg"),
                "-vf", f"scale={options['video_width']}:-2:force_original_aspect_ratio=decrease,format=yuv420p",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", str(options["video_crf"]),
                "-movflags", "+faststart", str(temp_output),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=600,
            check=False,
        )
        if process.returncode != 0 or not temp_output.is_file():
            raise RuntimeError(_safe_error(process.stderr, ""))
    finally:
        progress_stop.set()
        progress_thread.join(timeout=1)


def start_timelapse_render(options=None, *, camera_id=None):
    config = public_config(camera_id)
    if config is None:
        return {"success": False, "error": "GrowCam wurde nicht gefunden."}
    camera_id = config["camera_id"]
    status = _status_for(camera_id)
    render_lock = _timelapse_lock_for(camera_id)
    batch_id = config.get("batch_id")
    if not batch_id:
        return {"success": False, "error": "Der Kamera ist kein Durchgang zugeordnet."}
    summary = timelapse_summary(batch_id, camera_id=camera_id)
    if summary["frame_count"] < 2:
        return {"success": False, "error": "Für ein Zeitraffer-Video werden mindestens zwei Aufnahmen benötigt."}
    try:
        render_options = _normalize_render_options(options)
    except ValueError as exc:
        return {"success": False, "error": str(exc)}
    start_date = str((options or {}).get("start_date") or "").strip()
    if start_date:
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start_date):
                raise ValueError("invalid format")
            date.fromisoformat(start_date)
        except ValueError:
            return {"success": False, "error": "Ungültiges Startdatum (JJJJ-MM-TT)."}
    render_options["start_date"] = start_date
    if not render_lock.acquire(blocking=False):
        return {"success": False, "error": "Ein Zeitraffer-Video wird bereits erstellt."}
    selected_frames = []
    try:
        for frame in sorted(_batch_dir(batch_id, camera_id).glob("frame-*.jpg")):
            day = time.strftime("%Y-%m-%d", time.localtime(frame.stat().st_mtime))
            if not start_date or day >= start_date:
                selected_frames.append(frame)
        if len(selected_frames) < 2:
            return {"success": False, "error": "Ab diesem Startdatum sind weniger als zwei Zeitrafferbilder vorhanden."}
    except OSError:
        return {"success": False, "error": "Zeitrafferbilder konnten nicht gelesen werden."}
    finally:
        if len(selected_frames) < 2:
            render_lock.release()
    with _config_lock:
        status["timelapse_rendering"] = True
        status["timelapse_error"] = None
        status["render_options"] = dict(render_options)
        status["timelapse_progress"] = 1
        status["timelapse_stage"] = "Bilder werden vorbereitet"
        status["timelapse_processed_frames"] = 0
        status["timelapse_total_frames"] = len(selected_frames)
        status["timelapse_started_at"] = time.time()
        status["timelapse_finished_at"] = None
    threading.Thread(
        target=_render_timelapse_worker,
        args=(config, render_options, selected_frames),
        name="growstar-growcam-timelapse",
        daemon=True,
    ).start()
    return {
        "success": True,
        "frame_count": len(selected_frames),
        "options": render_options,
    }


def _recording_files(camera_id, batch_id=None):
    base = recording_dir_path(camera_id)
    if batch_id:
        directories = [base / f"batch_{int(batch_id)}"]
    else:
        directories = [
            path for path in base.glob("batch_*")
            if path.is_dir() and path.name[6:].isdigit()
        ] if base.is_dir() else []
    files = []
    for directory in directories:
        files.extend(directory.glob("recording-*.mp4"))
    return sorted(files, reverse=True)


def resolve_recording(camera_id, batch_id, filename):
    name = _safe_media_name(filename, prefix="recording-", suffix=".mp4")
    if name is None:
        return None
    candidate = recording_dir_path(camera_id) / f"batch_{int(batch_id)}" / name
    return candidate if candidate.is_file() else None


def list_recordings(*, camera_id=None, batch_id=None, page=1, per_page=24):
    candidates = []
    camera_ids = [camera_id] if camera_id else [item["camera_id"] for item in list_public_configs()]
    try:
        for current_camera_id in camera_ids:
            for video in _recording_files(current_camera_id, batch_id):
                directory_batch_id = int(video.parent.name[6:])
                stat = video.stat()
                candidates.append({
                    "camera_id": current_camera_id,
                    "batch_id": directory_batch_id,
                    "filename": video.name,
                    "created_at": stat.st_mtime,
                    "size_bytes": stat.st_size,
                })
    except (OSError, TypeError, ValueError):
        candidates = []
    candidates.sort(key=lambda item: item["created_at"], reverse=True)
    per_page = max(6, min(int(per_page), 100))
    pages = (len(candidates) + per_page - 1) // per_page
    page = max(1, min(int(page), pages or 1))
    start = (page - 1) * per_page
    return {
        "items": candidates[start:start + per_page],
        "page": page,
        "pages": pages,
        "total": len(candidates),
    }


def delete_recording(camera_id, batch_id, filename):
    if _recording_lock_for(camera_id).locked():
        return {"success": False, "error": "Während der Aufnahme kann kein Video gelöscht werden."}
    video = resolve_recording(camera_id, batch_id, filename)
    if video is None:
        return {"success": False, "error": "Videoaufnahme wurde nicht gefunden."}
    try:
        video.unlink()
    except OSError as exc:
        return {"success": False, "error": f"Videoaufnahme konnte nicht gelöscht werden: {exc}"}
    return {"success": True, "filename": video.name}


def _recording_worker(config, batch_id, duration_sec):
    camera_id = config["camera_id"]
    status = _status_for(camera_id)
    recording_lock = _recording_lock_for(camera_id)
    directory = recording_dir_path(camera_id) / f"batch_{int(batch_id)}"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    output = directory / f"recording-{stamp}.mp4"
    temp_output = directory / f".recording-{stamp}.mp4"
    try:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("FFmpeg ist nicht installiert.")
        process = subprocess.run(
            [
                ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-rtsp_transport", "tcp", "-i", _rtsp_url(config),
                "-t", str(duration_sec), "-map", "0:v:0", "-an",
                "-c:v", "copy", "-movflags", "+faststart", str(temp_output),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=duration_sec + 30,
            check=False,
        )
        if process.returncode != 0 or not temp_output.is_file() or temp_output.stat().st_size < 1024:
            raise RuntimeError(_safe_error(process.stderr, _rtsp_url(config)))
        os.chmod(temp_output, 0o640)
        os.replace(temp_output, output)
        with _config_lock:
            status["last_recording"] = {
                "batch_id": int(batch_id),
                "filename": output.name,
                "created_at": output.stat().st_mtime,
            }
            status["recording_error"] = None
    except subprocess.TimeoutExpired:
        with _config_lock:
            status["recording_error"] = "Videoaufnahme hat das Zeitlimit überschritten."
    except Exception as exc:
        with _config_lock:
            status["recording_error"] = str(exc).strip() or type(exc).__name__
    finally:
        try:
            if temp_output.is_file():
                temp_output.unlink()
        except OSError:
            pass
        with _config_lock:
            status["recording"] = False
            status["recording_started_at"] = None
            status["recording_duration_sec"] = None
        recording_lock.release()


def start_video_recording(duration_sec, batch_id, *, camera_id=None):
    config = public_config(camera_id)
    if config is None:
        return {"success": False, "error": "GrowCam wurde nicht gefunden."}
    if not config.get("enabled") or not config.get("host"):
        return {"success": False, "error": "GrowCam ist nicht aktiviert."}
    try:
        duration_sec = int(duration_sec)
        batch_id = int(batch_id)
    except (TypeError, ValueError):
        return {"success": False, "error": "Dauer oder Durchgang ist ungültig."}
    if duration_sec < 30 or duration_sec > 600:
        return {"success": False, "error": "Die Aufnahmedauer muss zwischen 30 Sekunden und 10 Minuten liegen."}
    if batch_id < 1:
        return {"success": False, "error": "Bitte einen Durchgang auswählen."}
    camera_id = config["camera_id"]
    recording_lock = _recording_lock_for(camera_id)
    if not recording_lock.acquire(blocking=False):
        return {"success": False, "error": "Diese Kamera nimmt bereits ein Video auf."}
    status = _status_for(camera_id)
    with _config_lock:
        status["recording"] = True
        status["recording_error"] = None
        status["recording_started_at"] = time.time()
        status["recording_duration_sec"] = duration_sec
    worker = threading.Thread(
        target=_recording_worker,
        args=(config, batch_id, duration_sec),
        name=f"growstar-growcam-recording-{camera_id}",
        daemon=True,
    )
    try:
        worker.start()
    except Exception as exc:
        with _config_lock:
            status["recording"] = False
            status["recording_error"] = str(exc).strip() or type(exc).__name__
            status["recording_started_at"] = None
            status["recording_duration_sec"] = None
        recording_lock.release()
        return {"success": False, "error": status["recording_error"]}
    return {"success": True, "camera_id": camera_id, "batch_id": batch_id, "duration_sec": duration_sec}


def mjpeg_stream(camera_id=None):
    config = public_config(camera_id)
    if config is None:
        raise RuntimeError("GrowCam wurde nicht gefunden.")
    camera_id = config["camera_id"]
    status = _status_for(camera_id)
    if not config.get("enabled") or not config.get("host"):
        raise RuntimeError("GrowCam ist nicht aktiviert oder nicht konfiguriert.")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg ist nicht installiert.")
    process = subprocess.Popen(
        [
            ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
            "-rtsp_transport", "tcp", "-i", _rtsp_url(config),
            "-an", "-sn", "-dn",
            "-vf", f"fps={config['live_fps']},scale={config['live_width']}:-2",
            "-q:v", "5", "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )
    with _config_lock:
        status["live_clients"] += 1
        status["live_error"] = None
    buffer = b""
    try:
        while process.stdout:
            chunk = process.stdout.read(65536)
            if not chunk:
                break
            buffer += chunk
            while True:
                start = buffer.find(b"\xff\xd8")
                end = buffer.find(b"\xff\xd9", start + 2) if start >= 0 else -1
                if start < 0 or end < 0:
                    if len(buffer) > 12_000_000:
                        buffer = buffer[-2:]
                    break
                frame = buffer[start:end + 2]
                buffer = buffer[end + 2:]
                yield (
                    b"--growcam\r\nContent-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii")
                    + frame + b"\r\n"
                )
        if process.poll() not in (None, 0):
            with _config_lock:
                status["live_error"] = "Der GrowCam-Livestream wurde unerwartet beendet."
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        with _config_lock:
            status["live_clients"] = max(0, status["live_clients"] - 1)


def growcam_loop():
    print("📷 GrowCam Snapshot-Thread gestartet")
    schedules = {}
    while True:
        now = time.monotonic()
        cameras = list_public_configs()
        active_ids = {camera["camera_id"] for camera in cameras}
        for stale_id in set(schedules) - active_ids:
            schedules.pop(stale_id, None)
        for config in cameras:
            camera_id = config["camera_id"]
            current_key = (
                config.get("enabled"), config.get("interval_sec"),
                config.get("timelapse_enabled"), config.get("timelapse_interval_sec"),
                config.get("batch_id"), config.get("host"),
            )
            schedule = schedules.setdefault(camera_id, {
                "key": None, "next_capture": 0.0, "next_archive": 0.0,
            })
            if current_key != schedule["key"]:
                schedule.update({"key": current_key, "next_capture": 0.0, "next_archive": 0.0})
            preview_due = now >= schedule["next_capture"]
            archive_due = (
                config.get("timelapse_enabled") and config.get("batch_id")
                and now >= schedule["next_archive"]
            )
            if config.get("enabled") and config.get("host") and (preview_due or archive_due):
                result = capture_snapshot(archive=bool(archive_due), camera_id=camera_id)
                if not result.get("success"):
                    print(f"⚠️ GrowCam {camera_id} Aufnahme fehlgeschlagen:", result.get("error"))
                finished = time.monotonic()
                if preview_due:
                    schedule["next_capture"] = finished + int(config.get("interval_sec") or 60)
                if archive_due:
                    schedule["next_archive"] = finished + int(config.get("timelapse_interval_sec") or 900)
            elif not config.get("enabled"):
                schedule["next_capture"] = schedule["next_archive"] = 0.0
        time.sleep(1)


load_config()


__all__ = (
    "LATEST_IMAGE",
    "PRIMARY_CAMERA_ID",
    "TIMELAPSE_DIR",
    "camera_for_tent",
    "capture_snapshot",
    "create_camera",
    "delete_recording",
    "delete_timelapse_frame",
    "delete_timelapse_video",
    "growcam_storage_summary",
    "list_all_timelapse_frames",
    "list_timelapse_videos",
    "growcam_loop",
    "latest_image_path",
    "list_recordings",
    "load_config",
    "list_timelapse_frames",
    "list_public_configs",
    "public_config",
    "mjpeg_stream",
    "recording_dir_path",
    "resolve_recording",
    "resolve_timelapse_video",
    "resolve_timelapse_frame",
    "save_config",
    "status_snapshot",
    "start_timelapse_render",
    "start_video_recording",
    "timelapse_summary",
)
