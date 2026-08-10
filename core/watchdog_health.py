# core/watchdog_health.py

"""Read-only health snapshots for the Growstar multi-station watchdog.

This module performs no relay switching and no network probes. It only reads
already available runtime/controller state. That keeps the watchdog safe and
cheap even when the UI polls it every few seconds.
"""

from __future__ import annotations

import threading
import time

import core.context as ctx

from core.constants import SENSOR_TIMEOUT
from core.devices import DEVICE_MODES
from core.hardware_assignments import DEVICE_HARDWARE
from core.runtime import list_runtimes
from core.tents import DEFAULT_TENT_ID, manager as tent_manager


CONTROL_LOOP_STALE_SEC = 10
MQTT_TRAFFIC_STALE_SEC = 30


_THREAD_SPECS = (
    ("watchdog", "Watchdog", ("growstar-watchdog",)),
    ("mqtt", "MQTT", ("growstar-mqtt",)),
    ("blu", "Bluetooth", ("growstar-blu",)),
    ("hardware", "Hardware", ("growstar-hardware",)),
    ("shelly", "Shelly", ("growstar-shelly",)),
)


def _safe_age(now, timestamp):
    try:
        timestamp = float(timestamp or 0)
    except (TypeError, ValueError):
        timestamp = 0

    if timestamp <= 0:
        return None

    return max(0.0, now - timestamp)


def _assignment(cfg, key):
    assignments = cfg.get("SENSOR_ASSIGNMENTS") or {}
    item = assignments.get(key) if isinstance(assignments, dict) else None
    if not isinstance(item, dict):
        item = {}

    return {
        "configured": bool(item.get("source_id")),
        "source_id": item.get("source_id"),
        "label": item.get("label") or item.get("source_id"),
        "field": item.get("field") or key,
    }


def _sensor_health(rt, key, *, now):
    st = rt.state
    cfg = rt.config

    if key == "temperature":
        timestamp = getattr(st, "last_ds_time", 0)
        stale_flag = bool(getattr(st, "temp_stale", False))
        value = st.live_state.get("temp")
    else:
        timestamp = getattr(st, "last_dht_time", 0)
        stale_flag = bool(getattr(st, "hum_stale", False))
        value = st.live_state.get("hum")

    assignment = _assignment(cfg, key)
    age = _safe_age(now, timestamp)
    stale = bool(
        assignment["configured"]
        and (
            age is None
            or age > SENSOR_TIMEOUT
            or stale_flag
        )
    )

    if not assignment["configured"]:
        state = "unconfigured"
    elif stale:
        state = "error"
    elif age is not None and age > min(10, max(1, SENSOR_TIMEOUT // 2)):
        state = "warn"
    else:
        state = "ok"

    return {
        **assignment,
        "value": value,
        "age": None if age is None else round(age, 1),
        "stale": stale,
        "state": state,
    }


def _config_health(rt):
    cfg = rt.config
    issues = []

    modes = cfg.get("DEVICE_MODES")
    if not isinstance(modes, dict):
        issues.append("DEVICE_MODES fehlt oder ist ungültig")
    else:
        for device, raw_mode in modes.items():
            if isinstance(raw_mode, dict):
                raw_mode = raw_mode.get("mode", "OFF")
            mode = str(raw_mode or "OFF").upper()
            if mode not in DEVICE_MODES:
                issues.append(f"{device}: ungültiger Modus {mode}")

    assignments = cfg.get("SENSOR_ASSIGNMENTS")
    if assignments is not None and not isinstance(assignments, dict):
        issues.append("SENSOR_ASSIGNMENTS ist ungültig")

    for device, meta in DEVICE_HARDWARE.items():
        host = str(cfg.get(meta["ip_key"]) or "").strip()
        relay = cfg.get(meta["relay_key"])

        # Nicht verwendete Aktoren dürfen vollständig offen sein.
        if not host and relay in (None, ""):
            continue

        if not host and relay not in (None, ""):
            issues.append(f"{device}: Relay ohne IP/Hostname")
            continue

        if host and relay in (None, ""):
            issues.append(f"{device}: IP/Hostname ohne Relay")
            continue

        try:
            relay_value = int(relay)
        except (TypeError, ValueError):
            issues.append(f"{device}: Relay ist keine Ganzzahl")
            continue

        if relay_value < 0 or relay_value > 15:
            issues.append(f"{device}: Relay außerhalb 0..15")

    return {
        "ok": not issues,
        "state": "ok" if not issues else "error",
        "issues": issues,
    }


def _hardware_health(rt):
    cfg = rt.config
    assigned = []

    for device, meta in DEVICE_HARDWARE.items():
        host = str(cfg.get(meta["ip_key"]) or "").strip()
        relay = cfg.get(meta["relay_key"])
        if not host or relay in (None, ""):
            continue

        try:
            relay = int(relay)
        except (TypeError, ValueError):
            continue

        assigned.append({
            "device": device,
            "label": meta["label"],
            "ip": host,
            "relay": relay,
        })

    if not assigned:
        state = "none"
    elif not rt.control_enabled:
        state = "shadow"
    else:
        # Phase 4E intentionally does not send additional network requests.
        # Reachability will later be sourced from the central hardware poll.
        state = "assigned"

    return {
        "state": state,
        "assigned": len(assigned),
        "endpoints": assigned,
        "actuation_blocked": not bool(rt.control_enabled),
        "reachability_checked": False,
    }


def _loop_health(rt, *, now):
    expected = bool(rt.enabled and (rt.control_enabled or rt.shadow_enabled))
    age = _safe_age(now, getattr(rt, "last_loop_ts", None))
    stale = bool(expected and (age is None or age > CONTROL_LOOP_STALE_SEC))

    if not expected:
        state = "inactive"
    elif stale:
        state = "error"
    elif age is not None and age > 5:
        state = "warn"
    else:
        state = "ok"

    return {
        "expected": expected,
        "mode": getattr(rt, "loop_mode", "inactive") or "inactive",
        "last_ts": getattr(rt, "last_loop_ts", None),
        "age": None if age is None else round(age, 1),
        "stale": stale,
        "state": state,
        "stale_after": CONTROL_LOOP_STALE_SEC,
    }


def station_health(rt, *, now=None):
    now = time.time() if now is None else float(now)

    temperature = _sensor_health(rt, "temperature", now=now)
    humidity = _sensor_health(rt, "humidity", now=now)
    loop = _loop_health(rt, now=now)
    config = _config_health(rt)
    hardware = _hardware_health(rt)

    sensor_failsafe = bool(temperature["stale"] or humidity["stale"])

    states = [loop["state"], temperature["state"], humidity["state"], config["state"]]
    if not rt.enabled:
        overall = "inactive"
    elif "error" in states:
        overall = "error"
    elif "warn" in states or "unconfigured" in states:
        overall = "warn"
    else:
        overall = "ok"

    return {
        "id": rt.tent_id,
        "name": rt.name or rt.tent_id,
        "enabled": bool(rt.enabled),
        "control_enabled": bool(rt.control_enabled),
        "shadow_enabled": bool(rt.shadow_enabled),
        "runtime_mode": "live" if rt.control_enabled else (
            "shadow" if rt.shadow_enabled else "inactive"
        ),
        "overall": overall,
        "loop": loop,
        "temperature": temperature,
        "humidity": humidity,
        "config": config,
        "hardware": hardware,
        "sensor_failsafe": {
            "active": sensor_failsafe,
            "state": "error" if sensor_failsafe else "ok",
            "reason": "Sensor stale" if sensor_failsafe else None,
        },
    }


def _thread_snapshot():
    names = {thread.name for thread in threading.enumerate() if thread.is_alive()}
    result = {}

    for key, label, accepted_names in _THREAD_SPECS:
        alive = any(name in names for name in accepted_names)
        result[key] = {
            "label": label,
            "alive": alive,
            "state": "ok" if alive else "error",
        }

    return result


def controller_health(*, now=None):
    now = time.time() if now is None else float(now)

    mqtt_age = _safe_age(now, getattr(ctx, "MQTT_LAST_MSG", 0))
    mqtt_stale = mqtt_age is None or mqtt_age > MQTT_TRAFFIC_STALE_SEC

    with ctx.energy_lock:
        energy = dict(ctx.energy_state)

    watchdog_age = _safe_age(now, getattr(ctx, "WATCHDOG_LAST_LOOP", 0))

    return {
        "threads": _thread_snapshot(),
        "mqtt": {
            "age": None if mqtt_age is None else round(mqtt_age, 1),
            "stale": mqtt_stale,
            "state": "warn" if mqtt_stale else "ok",
            "stale_after": MQTT_TRAFFIC_STALE_SEC,
        },
        "watchdog": {
            "age": None if watchdog_age is None else round(watchdog_age, 1),
            "stale": watchdog_age is None or watchdog_age > 15,
        },
        "energy": {
            "devices": len(energy),
            "stale": len(energy) == 0,
            "state": "warn" if len(energy) == 0 else "ok",
        },
    }


def build_watchdog_snapshot(*, now=None):
    now = time.time() if now is None else float(now)

    runtimes = sorted(list_runtimes(), key=lambda runtime: runtime.tent_id)
    stations = [station_health(runtime, now=now) for runtime in runtimes]
    controller = controller_health(now=now)

    # Legacy fields keep existing API consumers functional. They mirror the
    # default station plus the existing controller MQTT/Energy status.
    default_station = next(
        (item for item in stations if item["id"] == DEFAULT_TENT_ID),
        stations[0] if stations else None,
    )

    if default_station:
        legacy_temp = {
            "age": default_station["temperature"]["age"],
            "stale": default_station["temperature"]["stale"],
        }
        legacy_hum = {
            "age": default_station["humidity"]["age"],
            "stale": default_station["humidity"]["stale"],
        }
    else:
        legacy_temp = {"age": None, "stale": True}
        legacy_hum = {"age": None, "stale": True}

    return {
        "timestamp": now,
        "controller": controller,
        "stations": stations,
        "station_count": len(stations),
        "temp": legacy_temp,
        "hum": legacy_hum,
        "mqtt": controller["mqtt"],
        "energy": controller["energy"],
    }
