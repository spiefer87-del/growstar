# core/watchdog_health.py

"""Read-only health snapshots for the Growstar multi-station watchdog.

This module performs no relay switching and no network probes. It only reads
already available runtime/controller state. Network reachability is supplied by
the central hardware poll and consumed here from a thread-safe cache.
"""

from __future__ import annotations

import threading
import time

import core.context as ctx

from core.constants import SENSOR_TIMEOUT
from core.devices import DEVICE_MODES
from core.hardware.actuator_health import actuator_poll_status, get_endpoint_health
from core.hardware_assignments import DEVICE_HARDWARE
from core.runtime import list_runtimes
from core.tents import DEFAULT_TENT_ID


CONTROL_LOOP_STALE_SEC = 10
MQTT_TRAFFIC_STALE_SEC = 30


_THREAD_SPECS = (
    ("watchdog", "Watchdog", ("growstar-watchdog",)),
    ("mqtt", "MQTT", ("growstar-mqtt",)),
    ("blu", "Bluetooth", ("growstar-blu",)),
    ("hardware", "Hardware", ("growstar-hardware",)),
    ("shelly", "Shelly", ("growstar-shelly",)),
    ("hardware_recovery", "Hardware Recovery", ("growstar-hw-recovery",)),
    ("live_arming", "LIVE Arming", ("growstar-live-arming",)),
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




def _safety_health(rt, *, now):
    """Safety-Status robust und weiterhin netzwerkfrei einlesen.

    Der Import ist absichtlich lazy: alte isolierte Watchdog-Regressionstests
    koennen core.runtime stubs verwenden, ohne den produktiven Safety-Core
    initialisieren zu muessen. Im Produktivbetrieb markiert ein fehlender oder
    defekter Safety-Core eine LIVE-Station klar als Fehler.
    """

    try:
        from core.safety import get_runtime_safety_snapshot
        return get_runtime_safety_snapshot(rt, now=now)
    except Exception as exc:
        live = bool(getattr(rt, "control_enabled", False))
        return {
            "state": "error" if live else "inactive",
            "active": live,
            "live": live,
            "stale": live,
            "age": None,
            "blocked_devices": [],
            "devices": {},
            "overrides": {},
            "reason": f"Safety-Status nicht verfuegbar: {exc}" if live else None,
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


def _hardware_health(rt, *, now):
    cfg = rt.config
    endpoints = []

    for device, meta in DEVICE_HARDWARE.items():
        host = str(cfg.get(meta["ip_key"]) or "").strip()
        relay = cfg.get(meta["relay_key"])
        if not host or relay in (None, ""):
            continue

        try:
            relay = int(relay)
        except (TypeError, ValueError):
            continue

        cached = get_endpoint_health(host, relay, now=now)
        if cached is None:
            endpoint_state = "unknown"
            reachable = None
            actual_state = None
            check_age = None
            success_age = None
            failures = 0
            last_error = None
            latency_ms = None
        else:
            endpoint_state = cached.get("state", "unknown")
            reachable = cached.get("reachable")
            actual_state = cached.get("actual_state")
            check_age = cached.get("check_age")
            success_age = cached.get("success_age")
            failures = int(cached.get("consecutive_failures") or 0)
            last_error = cached.get("last_error")
            latency_ms = cached.get("latency_ms")

        endpoints.append({
            "device": device,
            "label": meta["label"],
            "ip": host,
            "relay": relay,
            "state": endpoint_state,
            "reachable": reachable,
            "actual_state": actual_state,
            "check_age": check_age,
            "success_age": success_age,
            "consecutive_failures": failures,
            "last_error": last_error,
            "latency_ms": latency_ms,
        })

    assigned = len(endpoints)
    online = sum(1 for item in endpoints if item["state"] == "ok")
    offline = sum(1 for item in endpoints if item["state"] == "error")
    stale = sum(1 for item in endpoints if item["state"] == "warn")
    unknown = sum(1 for item in endpoints if item["state"] == "unknown")

    if not endpoints:
        state = "none"
    elif offline:
        state = "error"
    elif stale or unknown:
        state = "warn"
    else:
        state = "ok"

    return {
        "state": state,
        "mode": "live" if rt.control_enabled else (
            "arming" if (getattr(rt, "arming", False) or getattr(rt, "live_requested", False))
            else ("shadow" if rt.shadow_enabled else "inactive")
        ),
        "assigned": assigned,
        "online": online,
        "offline": offline,
        "stale": stale,
        "unknown": unknown,
        "endpoints": endpoints,
        "actuation_blocked": not bool(rt.control_enabled),
        "reachability_checked": bool(assigned and not unknown),
    }


def _loop_health(rt, *, now):
    expected = bool(
        rt.enabled
        and (
            rt.control_enabled
            or rt.shadow_enabled
            or getattr(rt, "live_requested", False)
            or getattr(rt, "arming", False)
        )
    )
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
    hardware = _hardware_health(rt, now=now)
    safety = _safety_health(rt, now=now)

    # Legacy-Anzeige bleibt kompatibel. Phase 4I besitzt zusaetzlich die
    # abhaengigkeitsbewusste Safety-Matrix pro aktivem Geraet.
    sensor_failsafe = bool(temperature["stale"] or humidity["stale"])

    states = [loop["state"], temperature["state"], humidity["state"], config["state"]]
    if hardware["state"] in ("error", "warn"):
        states.append(hardware["state"])
    if safety.get("state") in ("error", "warn"):
        states.append(safety.get("state"))

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
        "live_requested": bool(getattr(rt, "live_requested", False)),
        "arming": bool(getattr(rt, "arming", False)),
        "runtime_mode": "live" if rt.control_enabled else (
            "arming" if (getattr(rt, "arming", False) or getattr(rt, "live_requested", False))
            else ("shadow" if rt.shadow_enabled else "inactive")
        ),
        "live_preflight": getattr(rt, "last_live_preflight", None),
        "overall": overall,
        "loop": loop,
        "temperature": temperature,
        "humidity": humidity,
        "config": config,
        "hardware": hardware,
        "safety": safety,
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


def _hardware_recovery_snapshot():
    try:
        from services.hardware_recovery import get_hardware_recovery_status
        return get_hardware_recovery_status()
    except Exception as exc:
        return {
            "running": False,
            "phase": "unavailable",
            "healthy": False,
            "last_error": str(exc),
            "known_gateways": 0,
            "online_gateways": 0,
            "expected_ble_devices": 0,
            "online_ble_devices": 0,
            "missing_ble_devices": [],
        }


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
        "hardware_recovery": _hardware_recovery_snapshot(),
        "actuator_poll": actuator_poll_status(now=now),
    }


def build_watchdog_snapshot(*, now=None):
    now = time.time() if now is None else float(now)

    runtimes = sorted(list_runtimes(), key=lambda runtime: runtime.tent_id)
    stations = [station_health(runtime, now=now) for runtime in runtimes]
    controller = controller_health(now=now)

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
