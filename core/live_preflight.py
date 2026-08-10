"""Read-only LIVE preflight for additional local Growstar stations.

The preflight never switches hardware and performs no network I/O.  It only
uses runtime state plus the read-only actuator-health cache populated by the
central hardware thread.
"""

from __future__ import annotations

import time

from core.constants import SENSOR_TIMEOUT
from core.devices import get_device_mode, get_device_params
from core.hardware.actuator_health import get_endpoint_health
from core.hardware_assignments import (
    DEVICE_HARDWARE,
    HardwareConflictError,
    validate_hardware_assignments,
)
from core.runtime import resolve_runtime


LIVE_LOOP_MAX_AGE_SEC = 8.0
_ALLOWED_MODES = {"OFF", "ON", "TIME", "INTERVAL", "ENV"}


def _age(now, timestamp):
    if not timestamp:
        return None
    return max(0.0, float(now) - float(timestamp))


def _active_devices(runtime):
    result = []
    for device in DEVICE_HARDWARE:
        mode = str(get_device_mode(device, runtime=runtime) or "OFF").upper()
        if mode != "OFF":
            result.append((device, mode))
    return result


def _sensor_requirements(runtime, active_devices):
    """Derives only the sensors really needed by active ENV devices."""

    cfg = runtime.config
    required = set()

    for device, mode in active_devices:
        if mode != "ENV":
            continue

        # Heating has dedicated temperature control logic.
        if device == "heating":
            required.add("temperature")
            continue

        # Light ENV is profile/time based and therefore sensor independent.
        if device == "light":
            continue

        env_cfg = (cfg.get("DEVICE_ENV_CONFIG") or {}).get(device) or {}
        if env_cfg.get("use_temp"):
            required.add("temperature")
        if env_cfg.get("use_hum"):
            required.add("humidity")

    return required


def _config_check(runtime, active_devices):
    cfg = runtime.config
    errors = []

    def minute_value(device, key, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            errors.append(f"{device}: {key} ist ungültig")
            return None
        if value < 0 or value > 1439:
            errors.append(f"{device}: {key} außerhalb 0..1439")
            return None
        return value

    for device, mode in active_devices:
        if mode not in _ALLOWED_MODES:
            errors.append(f"{device}: unbekannter Modus {mode}")
            continue

        params = get_device_params(device, runtime=runtime)
        if mode == "TIME":
            minute_value(device, "start_min", params.get("start_min", 0))
            minute_value(device, "end_min", params.get("end_min", 0))
        elif mode == "INTERVAL":
            try:
                on_sec = int(params.get("interval_on", 300))
                off_sec = int(params.get("interval_off", 900))
            except (TypeError, ValueError):
                errors.append(f"{device}: Intervallzeiten sind ungültig")
            else:
                if on_sec <= 0 or off_sec <= 0:
                    errors.append(f"{device}: Intervallzeiten müssen > 0 sein")

    # Profile/time-based light ENV still needs valid day/night boundaries.
    if any(device == "light" and mode == "ENV" for device, mode in active_devices):
        minute_value("light", "DAY_START_MIN", cfg.get("DAY_START_MIN", 360))
        minute_value("light", "NIGHT_START_MIN", cfg.get("NIGHT_START_MIN", 1320))

    numeric_keys = (
        "DAY_TEMP",
        "DAY_TEMP_TOL",
        "DAY_HUM",
        "DAY_HUM_TOL",
        "NIGHT_TEMP",
        "NIGHT_TEMP_TOL",
        "NIGHT_HUM",
        "NIGHT_HUM_TOL",
        "MIN_TEMP",
        "MAX_TEMP",
    )
    values = {}
    for key in numeric_keys:
        try:
            values[key] = float(cfg[key])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{key}: ungültig oder fehlt")

    if "MIN_TEMP" in values and "MAX_TEMP" in values:
        if values["MIN_TEMP"] >= values["MAX_TEMP"]:
            errors.append("MIN_TEMP muss kleiner als MAX_TEMP sein")

    return {
        "ok": not errors,
        "errors": errors,
    }


def _loop_check(runtime, now):
    age = _age(now, runtime.last_loop_ts)
    ok = bool(
        runtime.enabled
        and age is not None
        and age <= LIVE_LOOP_MAX_AGE_SEC
    )
    return {
        "ok": ok,
        "age": None if age is None else round(age, 1),
        "max_age": LIVE_LOOP_MAX_AGE_SEC,
        "mode": runtime.loop_mode,
    }


def _sensor_check(runtime, sensor, now):
    st = runtime.state
    assignments = runtime.config.get("SENSOR_ASSIGNMENTS") or {}
    assignment = assignments.get(sensor) if isinstance(assignments, dict) else None

    if sensor == "temperature":
        timestamp = st.last_ds_time
        stale = bool(st.temp_stale)
        value = st.live_state.get("temp")
    else:
        timestamp = st.last_dht_time
        stale = bool(st.hum_stale)
        value = st.live_state.get("hum")

    age = _age(now, timestamp)
    assigned = bool(
        isinstance(assignment, dict)
        and str(assignment.get("source_id") or "").strip()
    )
    ok = bool(
        assigned
        and value is not None
        and not stale
        and age is not None
        and age <= float(SENSOR_TIMEOUT)
    )

    return {
        "ok": ok,
        "assigned": assigned,
        "value": value,
        "stale": stale,
        "age": None if age is None else round(age, 1),
        "max_age": float(SENSOR_TIMEOUT),
        "source_id": (
            str(assignment.get("source_id") or "")
            if isinstance(assignment, dict)
            else None
        ),
    }


def _hardware_check(runtime, active_devices, now):
    cfg = runtime.config
    items = []
    blockers = []

    for device, mode in active_devices:
        meta = DEVICE_HARDWARE[device]
        host = str(cfg.get(meta["ip_key"]) or "").strip()
        relay = cfg.get(meta["relay_key"])

        if not host or relay in (None, ""):
            items.append({
                "device": device,
                "label": meta["label"],
                "mode": mode,
                "configured": False,
                "ok": False,
                "state": "unconfigured",
                "ip": host or None,
                "relay": None,
            })
            blockers.append(f"{meta['label']}: keine Hardware-Zuordnung")
            continue

        try:
            relay = int(relay)
        except (TypeError, ValueError):
            items.append({
                "device": device,
                "label": meta["label"],
                "mode": mode,
                "configured": False,
                "ok": False,
                "state": "invalid",
                "ip": host,
                "relay": relay,
            })
            blockers.append(f"{meta['label']}: ungültiges Relay")
            continue

        health = get_endpoint_health(host, relay, now=now)
        ok = bool(
            health
            and health.get("state") == "ok"
            and health.get("reachable") is True
            and isinstance(health.get("actual_state"), bool)
        )

        item = {
            "device": device,
            "label": meta["label"],
            "mode": mode,
            "configured": True,
            "ok": ok,
            "state": health.get("state") if health else "unknown",
            "ip": host,
            "relay": relay,
            "actual_state": health.get("actual_state") if health else None,
            "check_age": health.get("check_age") if health else None,
            "last_error": health.get("last_error") if health else None,
        }
        items.append(item)

        if not ok:
            reason = item["last_error"] or item["state"] or "nicht geprüft"
            blockers.append(
                f"{meta['label']}: {host} / Relay {relay} nicht bereit ({reason})"
            )

    return {
        "ok": all(item["ok"] for item in items),
        "required": len(items),
        "items": items,
        "blockers": blockers,
    }


def evaluate_live_preflight(runtime=None, *, now=None):
    """Returns a complete, read-only readiness snapshot for one runtime."""

    rt = resolve_runtime(runtime)
    now = time.time() if now is None else float(now)
    blockers = []

    if not rt.enabled:
        blockers.append("Station ist deaktiviert")

    loop = _loop_check(rt, now)
    if not loop["ok"]:
        blockers.append("Regelkreis-Heartbeat fehlt oder ist zu alt")

    active_devices = _active_devices(rt)
    config = _config_check(rt, active_devices)
    blockers.extend(config["errors"])

    required_sensors = _sensor_requirements(rt, active_devices)
    sensors = {}
    for sensor in ("temperature", "humidity"):
        if sensor not in required_sensors:
            sensors[sensor] = {
                "required": False,
                "ok": True,
            }
            continue

        result = _sensor_check(rt, sensor, now)
        result["required"] = True
        sensors[sensor] = result
        if not result["ok"]:
            label = "Temperatur" if sensor == "temperature" else "Luftfeuchte"
            blockers.append(f"{label}sensor nicht frisch/bereit")

    try:
        validate_hardware_assignments()
        conflicts = {"ok": True, "error": None}
    except HardwareConflictError as exc:
        conflicts = {"ok": False, "error": str(exc)}
        blockers.append(str(exc))

    hardware = _hardware_check(rt, active_devices, now)
    blockers.extend(hardware["blockers"])

    # Stable order, no duplicate UI messages.
    blockers = list(dict.fromkeys(blockers))

    return {
        "success": True,
        "tent_id": rt.tent_id,
        "name": rt.name,
        "ready": not blockers,
        "timestamp": now,
        "runtime": {
            "enabled": bool(rt.enabled),
            "control_enabled": bool(rt.control_enabled),
            "shadow_enabled": bool(rt.shadow_enabled),
            "live_requested": bool(getattr(rt, "live_requested", False)),
            "arming": bool(getattr(rt, "arming", False)),
        },
        "loop": loop,
        "config": config,
        "sensors": sensors,
        "hardware": hardware,
        "conflicts": conflicts,
        "active_devices": [
            {"device": device, "mode": mode}
            for device, mode in active_devices
        ],
        "blockers": blockers,
    }
