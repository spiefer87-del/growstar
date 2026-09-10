"""Lokaler Snapshot-Dienst für die VIVOSUN GrowCam C4 (VSC-GCC4)."""

from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from urllib.parse import quote


ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "instance" / "growcam.json"
CAMERA_DIR = ROOT / "instance" / "growcam"
LATEST_IMAGE = CAMERA_DIR / "latest.jpg"
TIMELAPSE_DIR = CAMERA_DIR / "timelapse"

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
    "last_video": None,
    "render_options": None,
}
_timelapse_lock = threading.Lock()


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


def _normalize_config(data):
    data = dict(data or {})
    result = dict(DEFAULT_CONFIG)
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

    if result["enabled"] and not result["host"]:
        raise ValueError("Vor dem Aktivieren muss eine Kamera-IP eingetragen sein.")
    return result


def load_config():
    global _config
    with _config_lock:
        data = {}
        if CONFIG_FILE.is_file():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception as exc:
                print("⚠️ GrowCam-Konfiguration konnte nicht gelesen werden:", exc)
        try:
            _config = _normalize_config(data)
        except ValueError as exc:
            print("⚠️ GrowCam-Konfiguration ist ungültig:", exc)
            _config = dict(DEFAULT_CONFIG)
        return dict(_config)


def save_config(data):
    global _config
    normalized = _normalize_config(data)
    with _config_lock:
        _atomic_write_json(CONFIG_FILE, normalized)
        _config = normalized
    return public_config()


def public_config():
    with _config_lock:
        return dict(_config)


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


def _batch_dir(batch_id):
    return TIMELAPSE_DIR / f"batch_{int(batch_id)}"


def _thumbnail_dir(batch_id):
    return _batch_dir(batch_id) / "thumbnails"


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
    batch_id = config.get("batch_id")
    if not config.get("timelapse_enabled") or not batch_id:
        return None
    directory = _batch_dir(batch_id)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(captured_at))
    target = directory / f"frame-{stamp}-{time.time_ns() % 1_000_000:06d}.jpg"
    shutil.copy2(LATEST_IMAGE, target)
    os.chmod(target, 0o640)
    _create_thumbnail(target, _thumbnail_dir(batch_id) / target.name)

    cutoff = captured_at - int(config.get("retention_days") or 120) * 86400
    for old_frame in directory.glob("frame-*.jpg"):
        try:
            if old_frame.stat().st_mtime < cutoff:
                old_frame.unlink()
                thumbnail = _thumbnail_dir(batch_id) / old_frame.name
                if thumbnail.is_file():
                    thumbnail.unlink()
        except OSError:
            pass
    return target


def capture_snapshot(*, archive=False):
    config = public_config()
    if not config.get("enabled"):
        return {"success": False, "error": "GrowCam ist nicht aktiviert."}
    if not config.get("host"):
        return {"success": False, "error": "GrowCam-IP fehlt."}
    if not _capture_lock.acquire(blocking=False):
        return {"success": False, "error": "Eine GrowCam-Aufnahme läuft bereits."}

    started = time.monotonic()
    temp_name = None
    with _config_lock:
        _status["capturing"] = True
    try:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("FFmpeg ist nicht installiert.")

        CAMERA_DIR.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=".growcam-frame-",
            suffix=".jpg",
            dir=str(CAMERA_DIR),
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
        os.replace(temp_name, LATEST_IMAGE)
        temp_name = None
        captured_at = time.time()
        archived = _archive_latest(config, captured_at) if archive else None
        with _config_lock:
            _status.update({
                "capturing": False,
                "last_capture": captured_at,
                "last_error": None,
                "last_duration_ms": round((time.monotonic() - started) * 1000),
                "width": width,
                "height": height,
                "last_archived": captured_at if archived else _status.get("last_archived"),
            })
        return {"success": True, **status_snapshot()}
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
            _status["capturing"] = False
        _capture_lock.release()

    with _config_lock:
        _status["last_error"] = error[:300]
    return {"success": False, "error": error, **status_snapshot()}


def status_snapshot():
    config = public_config()
    with _config_lock:
        status = dict(_status)
    image_exists = LATEST_IMAGE.is_file()
    if image_exists and not status.get("last_capture"):
        status["last_capture"] = LATEST_IMAGE.stat().st_mtime
    batch_id = config.get("batch_id")
    archive = timelapse_summary(batch_id)
    return {
        **status,
        "enabled": bool(config.get("enabled")),
        "configured": bool(config.get("host")),
        "name": config.get("name"),
        "tent_id": config.get("tent_id"),
        "interval_sec": config.get("interval_sec"),
        "batch_id": batch_id,
        "timelapse_enabled": bool(config.get("timelapse_enabled")),
        "timelapse_interval_sec": config.get("timelapse_interval_sec"),
        "retention_days": config.get("retention_days"),
        "live_width": config.get("live_width"),
        "live_fps": config.get("live_fps"),
        "timelapse": archive,
        "image_available": image_exists,
        "image_version": int(LATEST_IMAGE.stat().st_mtime) if image_exists else None,
    }


def _video_files(batch_id):
    if not batch_id:
        return []
    return sorted(_batch_dir(batch_id).glob("timelapse-*.mp4"), reverse=True)


def timelapse_summary(batch_id=None):
    try:
        directory = _batch_dir(batch_id) if batch_id else None
        frames = list(directory.glob("frame-*.jpg")) if directory and directory.is_dir() else []
        videos = _video_files(batch_id)
    except (OSError, TypeError, ValueError):
        frames, videos = [], []
    latest_video = videos[0] if videos else None
    return {
        "frame_count": len(frames),
        "latest_video": latest_video.name if latest_video else None,
        "latest_video_mtime": latest_video.stat().st_mtime if latest_video else None,
    }


def resolve_timelapse_video(batch_id, filename):
    name = _safe_media_name(filename, prefix="timelapse-", suffix=".mp4")
    if name is None:
        return None
    candidate = _batch_dir(batch_id) / name
    return candidate if candidate.is_file() else None


def list_timelapse_frames(batch_id, *, page=1, per_page=24):
    if not batch_id:
        return {"items": [], "page": 1, "pages": 0, "total": 0}
    try:
        frames = sorted(_batch_dir(batch_id).glob("frame-*.jpg"), reverse=True)
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


def resolve_timelapse_frame(batch_id, filename, *, thumbnail=False):
    name = _safe_media_name(filename, prefix="frame-", suffix=".jpg")
    if name is None:
        return None
    source = _batch_dir(batch_id) / name
    if not source.is_file():
        return None
    if not thumbnail:
        return source
    target = _thumbnail_dir(batch_id) / name
    if not target.is_file():
        try:
            _create_thumbnail(source, target)
        except Exception:
            return source
    return target


def delete_timelapse_frame(batch_id, filename):
    if _timelapse_lock.locked():
        return {"success": False, "error": "Während der Videoerstellung können keine Bilder gelöscht werden."}
    frame = resolve_timelapse_frame(batch_id, filename)
    if frame is None:
        return {"success": False, "error": "Zeitrafferbild wurde nicht gefunden."}
    thumbnail = _thumbnail_dir(batch_id) / frame.name
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


def _render_timelapse_worker(config, options):
    batch_id = config["batch_id"]
    directory = _batch_dir(batch_id)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    output = directory / f"timelapse-{stamp}.mp4"
    temp_output = directory / f".timelapse-{stamp}.mp4"
    try:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("FFmpeg ist nicht installiert.")
        process = subprocess.run(
            [
                ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-framerate", str(options["video_fps"]),
                "-pattern_type", "glob", "-i", str(directory / "frame-*.jpg"),
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
            raise RuntimeError(_safe_error(process.stderr, _rtsp_url(config)))
        os.chmod(temp_output, 0o640)
        os.replace(temp_output, output)
        for old_video in _video_files(batch_id)[5:]:
            try:
                old_video.unlink()
            except OSError:
                pass
        with _config_lock:
            _status["last_video"] = output.name
            _status["timelapse_error"] = None
    except subprocess.TimeoutExpired:
        with _config_lock:
            _status["timelapse_error"] = "Zeitraffer-Erstellung hat nach zehn Minuten nicht geantwortet."
    except Exception as exc:
        with _config_lock:
            _status["timelapse_error"] = str(exc).strip() or type(exc).__name__
    finally:
        try:
            if temp_output.is_file():
                temp_output.unlink()
        except OSError:
            pass
        with _config_lock:
            _status["timelapse_rendering"] = False
            _status["render_options"] = None
        _timelapse_lock.release()


def start_timelapse_render(options=None):
    config = public_config()
    batch_id = config.get("batch_id")
    if not batch_id:
        return {"success": False, "error": "Der Kamera ist kein Durchgang zugeordnet."}
    summary = timelapse_summary(batch_id)
    if summary["frame_count"] < 2:
        return {"success": False, "error": "Für ein Zeitraffer-Video werden mindestens zwei Aufnahmen benötigt."}
    try:
        render_options = _normalize_render_options(options)
    except ValueError as exc:
        return {"success": False, "error": str(exc)}
    if not _timelapse_lock.acquire(blocking=False):
        return {"success": False, "error": "Ein Zeitraffer-Video wird bereits erstellt."}
    with _config_lock:
        _status["timelapse_rendering"] = True
        _status["timelapse_error"] = None
        _status["render_options"] = dict(render_options)
    threading.Thread(
        target=_render_timelapse_worker,
        args=(config, render_options),
        name="growstar-growcam-timelapse",
        daemon=True,
    ).start()
    return {
        "success": True,
        "frame_count": summary["frame_count"],
        "options": render_options,
    }


def mjpeg_stream():
    config = public_config()
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
        _status["live_clients"] += 1
        _status["live_error"] = None
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
                _status["live_error"] = "Der GrowCam-Livestream wurde unerwartet beendet."
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        with _config_lock:
            _status["live_clients"] = max(0, _status["live_clients"] - 1)


def growcam_loop():
    print("📷 GrowCam Snapshot-Thread gestartet")
    next_capture = 0.0
    next_archive = 0.0
    schedule_key = None
    while True:
        config = public_config()
        now = time.monotonic()
        current_key = (
            config.get("enabled"), config.get("interval_sec"),
            config.get("timelapse_enabled"), config.get("timelapse_interval_sec"),
            config.get("batch_id"),
        )
        if current_key != schedule_key:
            next_capture = next_archive = 0.0
            schedule_key = current_key
        preview_due = now >= next_capture
        archive_due = (
            config.get("timelapse_enabled") and config.get("batch_id")
            and now >= next_archive
        )
        if config.get("enabled") and config.get("host") and (preview_due or archive_due):
            result = capture_snapshot(archive=bool(archive_due))
            if not result.get("success"):
                print("⚠️ GrowCam-Aufnahme fehlgeschlagen:", result.get("error"))
            finished = time.monotonic()
            if preview_due:
                next_capture = finished + int(config.get("interval_sec") or 60)
            if archive_due:
                next_archive = finished + int(config.get("timelapse_interval_sec") or 900)
        elif not config.get("enabled"):
            next_capture = next_archive = 0.0
        time.sleep(1)


load_config()


__all__ = (
    "LATEST_IMAGE",
    "TIMELAPSE_DIR",
    "capture_snapshot",
    "delete_timelapse_frame",
    "growcam_loop",
    "load_config",
    "list_timelapse_frames",
    "public_config",
    "mjpeg_stream",
    "resolve_timelapse_video",
    "resolve_timelapse_frame",
    "save_config",
    "status_snapshot",
    "start_timelapse_render",
    "timelapse_summary",
)
