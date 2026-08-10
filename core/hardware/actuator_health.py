# core/hardware/actuator_health.py

"""Thread-safe read-only health cache for assigned Shelly actuator endpoints.

The cache is controller-wide because one Raspberry owns all network polling.
Station ownership stays separate and is attached by the polling service.
No function in this module performs network I/O or relay switching.
"""

from __future__ import annotations

from copy import deepcopy
import threading
import time


ACTUATOR_HEALTH_STALE_SEC = 75

_lock = threading.RLock()
_endpoint_state = {}
_poll_state = {
    "running": False,
    "last_start_ts": None,
    "last_finish_ts": None,
    "duration_ms": None,
    "endpoints": 0,
    "online": 0,
    "offline": 0,
    "unknown": 0,
    "last_error": None,
}


def _normalize(host, relay):
    host = str(host or "").strip().lower()
    if not host:
        raise ValueError("host darf nicht leer sein")
    return host, int(relay)


def endpoint_key(host, relay):
    host, relay = _normalize(host, relay)
    return f"{host}|{relay}"


def clear_actuator_health():
    """Nur für Tests / kontrollierte Reinitialisierung."""
    with _lock:
        _endpoint_state.clear()
        _poll_state.update({
            "running": False,
            "last_start_ts": None,
            "last_finish_ts": None,
            "duration_ms": None,
            "endpoints": 0,
            "online": 0,
            "offline": 0,
            "unknown": 0,
            "last_error": None,
        })


def record_probe(
    host,
    relay,
    *,
    reachable,
    actual_state=None,
    error=None,
    latency_ms=None,
    owners=None,
    now=None,
):
    """Speichert das Ergebnis genau eines read-only Relay-Probes."""

    now = time.time() if now is None else float(now)
    host, relay = _normalize(host, relay)
    key = endpoint_key(host, relay)

    with _lock:
        previous = _endpoint_state.get(key, {})
        failures = int(previous.get("consecutive_failures") or 0)

        if reachable:
            failures = 0
            last_success_ts = now
            last_failure_ts = previous.get("last_failure_ts")
            last_error = None
        else:
            failures += 1
            last_success_ts = previous.get("last_success_ts")
            last_failure_ts = now
            last_error = str(error or "Keine Antwort / ungültiger Relay-Status")

        item = {
            "key": key,
            "host": host,
            "relay": relay,
            "reachable": bool(reachable),
            "actual_state": actual_state if isinstance(actual_state, bool) else None,
            "last_check_ts": now,
            "last_success_ts": last_success_ts,
            "last_failure_ts": last_failure_ts,
            "consecutive_failures": failures,
            "last_error": last_error,
            "latency_ms": None if latency_ms is None else round(float(latency_ms), 1),
            "owners": deepcopy(list(owners or previous.get("owners") or [])),
        }
        _endpoint_state[key] = item
        return deepcopy(item)


def _decorate(item, *, now, stale_after):
    if not item:
        return None

    result = deepcopy(item)
    checked = result.get("last_check_ts")
    success = result.get("last_success_ts")

    result["check_age"] = None if not checked else round(max(0.0, now - float(checked)), 1)
    result["success_age"] = None if not success else round(max(0.0, now - float(success)), 1)
    result["stale_after"] = float(stale_after)
    result["stale"] = bool(
        result["check_age"] is None
        or result["check_age"] > float(stale_after)
    )

    if result["last_check_ts"] is None:
        result["state"] = "unknown"
    elif result["reachable"] is False:
        result["state"] = "error"
    elif result["stale"]:
        result["state"] = "warn"
    else:
        result["state"] = "ok"

    return result


def get_endpoint_health(host, relay, *, now=None, stale_after=ACTUATOR_HEALTH_STALE_SEC):
    now = time.time() if now is None else float(now)
    try:
        key = endpoint_key(host, relay)
    except (TypeError, ValueError):
        return None

    with _lock:
        item = deepcopy(_endpoint_state.get(key))

    return _decorate(item, now=now, stale_after=stale_after)


def actuator_health_snapshot(*, now=None, stale_after=ACTUATOR_HEALTH_STALE_SEC):
    now = time.time() if now is None else float(now)
    with _lock:
        values = [deepcopy(item) for item in _endpoint_state.values()]

    return [
        _decorate(item, now=now, stale_after=stale_after)
        for item in sorted(values, key=lambda value: (value["host"], value["relay"]))
    ]


def mark_poll_started(*, endpoint_count=0, now=None):
    now = time.time() if now is None else float(now)
    with _lock:
        _poll_state.update({
            "running": True,
            "last_start_ts": now,
            "endpoints": int(endpoint_count),
            "last_error": None,
        })


def mark_poll_finished(*, online=0, offline=0, unknown=0, error=None, now=None):
    now = time.time() if now is None else float(now)
    with _lock:
        started = _poll_state.get("last_start_ts")
        duration = None if not started else max(0.0, (now - float(started)) * 1000.0)
        _poll_state.update({
            "running": False,
            "last_finish_ts": now,
            "duration_ms": None if duration is None else round(duration, 1),
            "online": int(online),
            "offline": int(offline),
            "unknown": int(unknown),
            "last_error": None if error is None else str(error),
        })


def actuator_poll_status(*, now=None):
    now = time.time() if now is None else float(now)
    with _lock:
        result = deepcopy(_poll_state)

    finished = result.get("last_finish_ts")
    result["age"] = None if not finished else round(max(0.0, now - float(finished)), 1)
    return result
