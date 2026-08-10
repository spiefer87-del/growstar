# services/actuator_health.py

"""Central read-only polling of all assigned actuator endpoints."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from core.actuators import get_shelly_relay_state
from core.hardware.actuator_health import (
    mark_poll_finished,
    mark_poll_started,
    record_probe,
)
from core.hardware_assignments import DEVICE_HARDWARE
from core.runtime import list_runtimes


ACTUATOR_PROBE_TIMEOUT_SEC = 1.5
ACTUATOR_PROBE_WORKERS = 4


def collect_assigned_endpoints(runtimes=None):
    """Sammelt eindeutige Host/Relay-Endpunkte über alle lokalen Stationen."""

    runtimes = list(list_runtimes() if runtimes is None else runtimes)
    endpoints = {}

    for runtime in runtimes:
        cfg = runtime.config
        for device, meta in DEVICE_HARDWARE.items():
            host = str(cfg.get(meta["ip_key"]) or "").strip()
            relay = cfg.get(meta["relay_key"])
            if not host or relay in (None, ""):
                continue

            try:
                relay = int(relay)
            except (TypeError, ValueError):
                continue

            key = (host.lower(), relay)
            entry = endpoints.setdefault(key, {
                "host": host,
                "relay": relay,
                "owners": [],
            })
            entry["owners"].append({
                "tent_id": runtime.tent_id,
                "device": device,
                "label": meta["label"],
                "control_enabled": bool(runtime.control_enabled),
                "shadow_enabled": bool(runtime.shadow_enabled),
            })

    return list(endpoints.values())


def _default_probe(host, relay, timeout):
    started = time.monotonic()
    state = get_shelly_relay_state(host, relay, timeout=timeout)
    latency_ms = (time.monotonic() - started) * 1000.0

    if isinstance(state, bool):
        return {
            "reachable": True,
            "actual_state": state,
            "error": None,
            "latency_ms": latency_ms,
        }

    return {
        "reachable": False,
        "actual_state": None,
        "error": "Keine Antwort / ungültiger Relay-Status",
        "latency_ms": latency_ms,
    }


def _run_probe(endpoint, probe, timeout):
    host = endpoint["host"]
    relay = endpoint["relay"]
    started = time.monotonic()

    try:
        result = probe(host, relay, timeout)
        if isinstance(result, bool):
            result = {
                "reachable": True,
                "actual_state": result,
                "error": None,
            }
        elif result is None:
            result = {
                "reachable": False,
                "actual_state": None,
                "error": "Keine Antwort / ungültiger Relay-Status",
            }
        elif not isinstance(result, dict):
            raise TypeError("Probe muss dict/bool/None zurückgeben")

        result = dict(result)
        result.setdefault("reachable", False)
        result.setdefault("actual_state", None)
        result.setdefault("error", None)
        result.setdefault("latency_ms", (time.monotonic() - started) * 1000.0)
        return endpoint, result

    except Exception as exc:
        return endpoint, {
            "reachable": False,
            "actual_state": None,
            "error": str(exc),
            "latency_ms": (time.monotonic() - started) * 1000.0,
        }


def poll_assigned_actuators(
    *,
    runtimes=None,
    probe=None,
    timeout=ACTUATOR_PROBE_TIMEOUT_SEC,
    max_workers=ACTUATOR_PROBE_WORKERS,
    now=None,
):
    """Prüft jeden zugeordneten Host/Relay-Endpunkt genau einmal.

    Diese Funktion ist ausschließlich read-only. Sie ruft niemals Switch.Set,
    Gen1 ``turn=`` oder irgendeine Failsafe-Korrektur auf.
    """

    endpoints = collect_assigned_endpoints(runtimes=runtimes)
    mark_poll_started(endpoint_count=len(endpoints), now=now)

    if not endpoints:
        mark_poll_finished(online=0, offline=0, unknown=0, now=now)
        return {"endpoints": 0, "online": 0, "offline": 0, "results": []}

    probe = probe or _default_probe
    workers = max(1, min(int(max_workers), len(endpoints)))
    results = []
    online = 0
    offline = 0

    try:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="growstar-actuator-probe") as pool:
            futures = [
                pool.submit(_run_probe, endpoint, probe, float(timeout))
                for endpoint in endpoints
            ]

            for future in as_completed(futures):
                endpoint, result = future.result()
                reachable = bool(result.get("reachable"))
                online += int(reachable)
                offline += int(not reachable)

                item = record_probe(
                    endpoint["host"],
                    endpoint["relay"],
                    reachable=reachable,
                    actual_state=result.get("actual_state"),
                    error=result.get("error"),
                    latency_ms=result.get("latency_ms"),
                    owners=endpoint.get("owners"),
                    now=now,
                )
                results.append(item)

        mark_poll_finished(online=online, offline=offline, unknown=0, now=now)
        return {
            "endpoints": len(endpoints),
            "online": online,
            "offline": offline,
            "results": results,
        }

    except Exception as exc:
        mark_poll_finished(
            online=online,
            offline=offline,
            unknown=max(0, len(endpoints) - online - offline),
            error=exc,
            now=now,
        )
        raise
