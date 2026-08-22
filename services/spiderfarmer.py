"""Growstar adapter for the canonical Spider Farmer SF.2 read model.

The Spider Farmer bridge is the transport/protocol boundary. This service only
reads its already-normalized ``spiderfarmer_state.json`` and publishes the
environment sensor as a normal Growstar controller-wide sensor source.

Important safety properties:
- read-only: no MQTT encoder, no socket, no command path;
- stale-safe: an unchanged Spider Farmer timestamp is never refreshed locally;
- fail-closed: missing/corrupt state simply produces no new Growstar source;
- no raw MQTT payloads are exposed through the sensor source.
"""

from __future__ import annotations

from copy import deepcopy
import datetime
import json
import os
from pathlib import Path
import threading
import time

from core.sensor_sources import update_sensor_source


_PROJECT_DIR = Path(__file__).resolve().parents[1]
_DEFAULT_STATE_PATH = (
    _PROJECT_DIR
    / "instance"
    / "spiderfarmer"
    / "spiderfarmer_state.json"
)

_STATE_PATH_ENV = "GROWSTAR_SPIDERFARMER_STATE_PATH"

_lock = threading.Lock()
_last_published_seen = {}


def state_path():
    configured = str(os.getenv(_STATE_PATH_ENV) or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return _DEFAULT_STATE_PATH


def load_state(path=None):
    """Load the canonical SF.2 state.

    Returns a defensive empty state on any read/parse/schema problem. Runtime
    control must never fail because Spider Farmer is offline.
    """

    path = Path(path or state_path())

    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError, TypeError):
        return _empty_state()

    if not isinstance(payload, dict):
        return _empty_state()

    controllers = payload.get("controllers")
    if not isinstance(controllers, dict):
        return _empty_state()

    return payload


def list_controllers(path=None):
    state = load_state(path)
    result = []

    for controller_id, controller in state.get("controllers", {}).items():
        if not isinstance(controller, dict):
            continue

        item = deepcopy(controller)
        item["id"] = str(item.get("id") or controller_id)
        item["source_id"] = sensor_source_id(item["id"])
        item["sensor_label"] = sensor_source_label(item)
        item["online"] = controller_is_online(item)
        result.append(item)

    result.sort(key=lambda item: str(item.get("id") or ""))
    return result


def controller(controller_id, path=None):
    wanted = str(controller_id or "").strip().lower()
    if not wanted:
        return None

    for item in list_controllers(path):
        if str(item.get("id") or "").lower() == wanted:
            return item
        if str(item.get("pid") or "").lower() == wanted:
            return item

    return None


def sensor_source_id(controller_id):
    clean = str(controller_id or "").strip().lower()
    return f"spiderfarmer:{clean}:environment"


def sensor_source_label(controller_data):
    controller_id = str((controller_data or {}).get("id") or "").strip()
    suffix = controller_id[-4:].upper() if controller_id else "GGS"
    return f"Spider Farmer GGS {suffix}"


def controller_is_online(controller_data, *, now=None, timeout=120):
    seen = _parse_timestamp((controller_data or {}).get("last_seen"))
    if seen is None:
        return False

    current = time.time() if now is None else float(now)
    return 0 <= (current - seen) <= float(timeout)


def public_snapshot(path=None):
    """Return normalized state suitable for future Growstar APIs/UI.

    The canonical state itself already excludes raw MQTT payloads and secrets.
    This method adds source metadata and an online flag without mutating it.
    """

    state = load_state(path)
    return {
        "success": True,
        "schema": state.get("schema"),
        "phase": state.get("phase"),
        "read_only": bool(state.get("read_only", True)),
        "state_path": str(Path(path or state_path())),
        "controllers": list_controllers(path),
    }


def sync_sensor_sources(path=None, *, now=None):
    """Publish only genuinely new Spider Farmer sensor samples into Growstar.

    ``update_sensor_source`` stamps sources with the current local time. Calling
    it repeatedly for an unchanged bridge sample would therefore make a dead
    controller look fresh forever. We explicitly suppress that.
    """

    current = time.time() if now is None else float(now)
    published = []
    skipped = []

    for item in list_controllers(path):
        controller_id = str(item.get("id") or "").strip().lower()
        last_seen = str(item.get("last_seen") or "").strip()

        if not controller_id or not last_seen:
            skipped.append({
                "id": controller_id or None,
                "reason": "missing_identity_or_timestamp",
            })
            continue

        sensor = ((item.get("live") or {}).get("sensor") or {})
        if not isinstance(sensor, dict):
            skipped.append({
                "id": controller_id,
                "reason": "no_sensor_block",
            })
            continue

        temperature = sensor.get("temperature_c")
        humidity = sensor.get("humidity_percent")

        if temperature is None and humidity is None:
            skipped.append({
                "id": controller_id,
                "reason": "no_supported_sensor_values",
            })
            continue

        with _lock:
            if _last_published_seen.get(controller_id) == last_seen:
                skipped.append({
                    "id": controller_id,
                    "reason": "unchanged",
                })
                continue

        source_id = sensor_source_id(controller_id)

        raw = {
            "provider": "spiderfarmer",
            "controller_id": controller_id,
            "pid": item.get("pid"),
            "prefix": item.get("prefix"),
            "bridge_last_seen": last_seen,
            "vpd_kpa": sensor.get("vpd_kpa"),
            "day_environment_target": sensor.get("day_environment_target"),
            "day_sensor": sensor.get("day_sensor"),
        }

        source = update_sensor_source(
            source_id,
            label=sensor_source_label(item),
            source_type="spiderfarmer",
            temperature=temperature,
            humidity=humidity,
            raw=raw,
        )

        with _lock:
            _last_published_seen[controller_id] = last_seen

        published.append({
            "controller_id": controller_id,
            "source_id": source_id,
            "temperature": source.get("temperature") if source else temperature,
            "humidity": source.get("humidity") if source else humidity,
            "bridge_last_seen": last_seen,
            "published_at": current,
        })

    return {
        "success": True,
        "published": published,
        "skipped": skipped,
        "controller_count": len(list_controllers(path)),
    }


def reset_sync_cache():
    """Regression/test helper; has no effect on bridge or controller state."""
    with _lock:
        _last_published_seen.clear()


def _parse_timestamp(value):
    text = str(value or "").strip()
    if not text:
        return None

    try:
        parsed = datetime.datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)

    return parsed.timestamp()


def _empty_state():
    return {
        "schema": 1,
        "phase": "SF.2",
        "read_only": True,
        "controllers": {},
    }
