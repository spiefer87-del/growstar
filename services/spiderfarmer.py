"""Growstar adapter for the canonical Spider Farmer read model.

SF.2A publishes the GGS environment sensor as a normal Growstar sensor source.
SF.3A additionally exposes a conservative read-only device inventory derived
from the already-normalized Spider Farmer state.

Important safety properties:
- read-only: no MQTT encoder, no socket, no command path;
- stale-safe: an unchanged Spider Farmer timestamp is never refreshed locally;
- fail-closed: missing/corrupt state simply produces no new Growstar source;
- no raw MQTT payloads are exposed through the public snapshot;
- device inventory is a projection only and never mutates bridge state.
"""

from __future__ import annotations

from copy import deepcopy
import datetime
import json
import os
from pathlib import Path
import threading
import time

from bridge.spiderfarmer.device_model import build_controller_devices
from bridge.spiderfarmer.device_model import device_by_id as _device_by_id
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
    """Load the canonical Spider Farmer state defensively."""

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

    for controller_id, controller_data in state.get("controllers", {}).items():
        if not isinstance(controller_data, dict):
            continue

        item = deepcopy(controller_data)
        item["id"] = str(item.get("id") or controller_id)
        item["source_id"] = sensor_source_id(item["id"])
        item["sensor_label"] = sensor_source_label(item)
        item["online"] = controller_is_online(item)
        item["devices"] = build_controller_devices(item)
        item["device_count"] = _count_devices(item["devices"])

        result.append(item)

    result.sort(
        key=lambda item: str(item.get("id") or "")
    )

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


def list_devices(controller_id=None, path=None):
    """Return the read-only SF.3A device inventory.

    When controller_id is omitted, devices from all observed controllers are
    returned with controller identity attached.
    """

    if controller_id is not None:
        item = controller(controller_id, path)

        if not item:
            return []

        return [
            _with_controller_identity(device, item)
            for device in item.get("devices") or []
        ]

    result = []

    for item in list_controllers(path):
        for device in item.get("devices") or []:
            result.append(
                _with_controller_identity(device, item)
            )

    return result


def device(controller_id, device_id, path=None):
    item = controller(controller_id, path)

    if not item:
        return None

    found = _device_by_id(
        item,
        device_id,
    )

    if not found:
        return None

    return _with_controller_identity(
        found,
        item,
    )


def sensor_source_id(controller_id):
    clean = str(controller_id or "").strip().lower()
    return f"spiderfarmer:{clean}:environment"


def sensor_source_label(controller_data):
    controller_id = str(
        (controller_data or {}).get("id") or ""
    ).strip()

    suffix = (
        controller_id[-4:].upper()
        if controller_id
        else "GGS"
    )

    return f"Spider Farmer GGS {suffix}"


def controller_is_online(controller_data, *, now=None, timeout=120):
    seen = _parse_timestamp(
        (controller_data or {}).get("last_seen")
    )

    if seen is None:
        return False

    current = (
        time.time()
        if now is None
        else float(now)
    )

    return (
        0
        <= (current - seen)
        <= float(timeout)
    )


def public_snapshot(path=None):
    """Return normalized read-only state suitable for Growstar APIs/UI."""

    state = load_state(path)

    return {
        "success": True,
        "schema": state.get("schema"),
        "phase": "SF.3A",
        "source_phase": state.get("phase"),
        "read_only": True,
        "state_path": str(
            Path(path or state_path())
        ),
        "controllers": list_controllers(path),
    }


def sync_sensor_sources(path=None, *, now=None):
    """Publish only genuinely new Spider Farmer sensor samples into Growstar."""

    current = (
        time.time()
        if now is None
        else float(now)
    )

    published = []
    skipped = []

    controllers = list_controllers(path)

    for item in controllers:
        controller_id = str(
            item.get("id") or ""
        ).strip().lower()

        last_seen = str(
            item.get("last_seen") or ""
        ).strip()

        if not controller_id or not last_seen:
            skipped.append({
                "id": controller_id or None,
                "reason": "missing_identity_or_timestamp",
            })
            continue

        sensor = (
            (item.get("live") or {})
            .get("sensor")
            or {}
        )

        if not isinstance(sensor, dict):
            skipped.append({
                "id": controller_id,
                "reason": "no_sensor_block",
            })
            continue

        temperature = sensor.get(
            "temperature_c"
        )

        humidity = sensor.get(
            "humidity_percent"
        )

        ppfd = sensor.get(
            "ppfd"
        )

        if (
            temperature is None
            and humidity is None
            and ppfd is None
        ):
            skipped.append({
                "id": controller_id,
                "reason": "no_supported_sensor_values",
            })
            continue

        with _lock:
            if (
                _last_published_seen.get(
                    controller_id
                )
                == last_seen
            ):
                skipped.append({
                    "id": controller_id,
                    "reason": "unchanged",
                })
                continue

        source_id = sensor_source_id(
            controller_id
        )

        raw = {
            "provider": "spiderfarmer",
            "controller_id": controller_id,
            "pid": item.get("pid"),
            "prefix": item.get("prefix"),
            "bridge_last_seen": last_seen,
            "vpd_kpa": sensor.get("vpd_kpa"),
            "day_environment_target": sensor.get(
                "day_environment_target"
            ),
            "day_sensor": sensor.get(
                "day_sensor"
            ),
        }

        source = update_sensor_source(
            source_id,
            label=sensor_source_label(item),
            source_type="spiderfarmer",
            temperature=temperature,
            humidity=humidity,
            ppfd=ppfd,
            raw=raw,
        )

        with _lock:
            _last_published_seen[
                controller_id
            ] = last_seen

        published.append({
            "controller_id": controller_id,
            "source_id": source_id,
            "temperature": (
                source.get("temperature")
                if source
                else temperature
            ),
            "humidity": (
                source.get("humidity")
                if source
                else humidity
            ),
            "ppfd": (
                source.get("ppfd")
                if source
                else ppfd
            ),
            "bridge_last_seen": last_seen,
            "published_at": current,
        })

    return {
        "success": True,
        "published": published,
        "skipped": skipped,
        "controller_count": len(
            controllers
        ),
    }


def reset_sync_cache():
    """Regression/test helper; has no effect on bridge or controller state."""

    with _lock:
        _last_published_seen.clear()


def _with_controller_identity(device_data, controller_data):
    result = deepcopy(device_data)

    result["controller_id"] = str(
        (controller_data or {}).get("id") or ""
    )

    result["controller_pid"] = (
        (controller_data or {}).get("pid")
    )

    result["controller_online"] = bool(
        (controller_data or {}).get("online")
    )

    return result


def _count_devices(devices):
    total = 0

    for item in devices or []:
        total += 1
        total += len(
            item.get("channels") or []
        )

    return total


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
        parsed = parsed.replace(
            tzinfo=datetime.timezone.utc
        )

    return parsed.timestamp()


def _empty_state():
    return {
        "schema": 1,
        "phase": "SF.2",
        "read_only": True,
        "controllers": {},
    }
