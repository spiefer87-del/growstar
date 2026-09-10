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

DEFAULT_CONFIG = {
    "enabled": False,
    "name": "VIVOSUN GrowCam C4",
    "host": "",
    "port": 554,
    "path": "/live/ch00_0",
    "username": "admin",
    "interval_sec": 60,
    "tent_id": "tent_1",
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
}


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


def capture_snapshot():
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
        with _config_lock:
            _status.update({
                "capturing": False,
                "last_capture": captured_at,
                "last_error": None,
                "last_duration_ms": round((time.monotonic() - started) * 1000),
                "width": width,
                "height": height,
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
    return {
        **status,
        "enabled": bool(config.get("enabled")),
        "configured": bool(config.get("host")),
        "name": config.get("name"),
        "tent_id": config.get("tent_id"),
        "interval_sec": config.get("interval_sec"),
        "image_available": image_exists,
        "image_version": int(LATEST_IMAGE.stat().st_mtime) if image_exists else None,
    }


def growcam_loop():
    print("📷 GrowCam Snapshot-Thread gestartet")
    next_capture = 0.0
    while True:
        config = public_config()
        now = time.monotonic()
        if config.get("enabled") and config.get("host") and now >= next_capture:
            result = capture_snapshot()
            if not result.get("success"):
                print("⚠️ GrowCam-Aufnahme fehlgeschlagen:", result.get("error"))
            next_capture = time.monotonic() + int(config.get("interval_sec") or 60)
        elif not config.get("enabled"):
            next_capture = 0.0
        time.sleep(1)


load_config()


__all__ = (
    "LATEST_IMAGE",
    "capture_snapshot",
    "growcam_loop",
    "load_config",
    "public_config",
    "save_config",
    "status_snapshot",
)
