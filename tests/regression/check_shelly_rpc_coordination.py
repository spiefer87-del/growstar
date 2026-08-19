#!/usr/bin/env python3
"""Growstar 3.9.4 / Phase 4V.4 – Shelly-RPC-Koordination und Health-Retry."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import sys
import threading
import time


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def ok(message):
    print("✅", message)


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    ok(message)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def syntax(rel):
    ast.parse(read(rel), filename=rel)
    ok(f"Python-Syntax {rel}")


def _test_lock():
    import core.context as ctx

    # Muss reentrant sein: ein normaler Lock würde hier hängen.
    with ctx.shelly_lock:
        acquired = ctx.shelly_lock.acquire(timeout=0.2)
        require(acquired, "Shelly-Transport-Lock ist reentrant")
        ctx.shelly_lock.release()

    active = 0
    max_active = 0
    counter_lock = threading.Lock()
    barrier = threading.Barrier(3)

    def worker():
        nonlocal active, max_active
        barrier.wait()
        with ctx.shelly_lock:
            with counter_lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.04)
            with counter_lock:
                active -= 1

    threads = [
        threading.Thread(target=worker, daemon=True),
        threading.Thread(target=worker, daemon=True),
    ]
    for thread in threads:
        thread.start()

    barrier.wait()
    for thread in threads:
        thread.join(timeout=1)

    require(
        max_active == 1,
        "Parallele Shelly-Abschnitte werden serialisiert",
    )


def _fake_response(status=200, payload=None):
    class Response:
        status_code = status
        text = ""

        def json(self):
            return payload

        def raise_for_status(self):
            if self.status_code >= 400:
                import requests
                raise requests.HTTPError(f"HTTP {self.status_code}")

    return Response()


def _test_diagnostic_probe():
    import requests
    import core.actuators as actuators

    original_get = actuators.requests.get

    try:
        actuators.requests.get = lambda *args, **kwargs: _fake_response(
            200,
            {"output": True},
        )

        result = actuators.probe_shelly_relay_state(
            "192.0.2.10",
            0,
            timeout=0.1,
        )
        require(
            result["reachable"] is True
            and result["actual_state"] is True
            and result["protocol"] == "gen2",
            "Diagnose-Probe übernimmt gültigen Gen2-Relay-Status",
        )

        def timeout_get(*args, **kwargs):
            raise requests.Timeout("simulierter Timeout")

        actuators.requests.get = timeout_get
        result = actuators.probe_shelly_relay_state(
            "192.0.2.10",
            0,
            timeout=0.1,
        )
        require(
            result["reachable"] is False
            and "Timeout" in str(result["error"]),
            "Timeout bleibt als konkreter Diagnosegrund erhalten",
        )

        require(
            actuators.get_shelly_relay_state(
                "192.0.2.10",
                0,
                timeout=0.1,
            ) is None,
            "Rückwärtskompatibler Relay-State-Wrapper bleibt bool/None",
        )

    finally:
        actuators.requests.get = original_get


def _test_health_retry():
    import services.actuator_health as health

    original_probe = health.probe_shelly_relay_state
    original_sleep = health.time.sleep

    try:
        calls = []

        def transient(host, relay, timeout):
            calls.append((host, relay, timeout))
            if len(calls) == 1:
                return {
                    "reachable": False,
                    "actual_state": None,
                    "error": "Gen2: Timeout nach 0.1s",
                    "protocol": None,
                }
            return {
                "reachable": True,
                "actual_state": False,
                "error": None,
                "protocol": "gen2",
            }

        health.probe_shelly_relay_state = transient
        health.time.sleep = lambda value: None

        result = health._default_probe(
            "192.0.2.20",
            0,
            0.1,
            retries=1,
            retry_delay=0,
        )
        require(
            len(calls) == 2
            and result["reachable"] is True
            and result["actual_state"] is False
            and result["attempts"] == 2,
            "Einzelaussetzer wird einmal wiederholt und bei Erfolg nicht als offline gemeldet",
        )

        calls.clear()

        def persistent(host, relay, timeout):
            calls.append((host, relay, timeout))
            return {
                "reachable": False,
                "actual_state": None,
                "error": "Gen2: Verbindungsfehler: simuliert",
                "protocol": None,
            }

        health.probe_shelly_relay_state = persistent
        result = health._default_probe(
            "192.0.2.20",
            0,
            0.1,
            retries=1,
            retry_delay=0,
        )
        require(
            len(calls) == 2
            and result["reachable"] is False
            and result["attempts"] == 2
            and "2 Versuche fehlgeschlagen" in result["error"]
            and "Verbindungsfehler" in result["error"],
            "Echter zweifacher Ausfall bleibt offline und behält den Diagnosegrund",
        )

    finally:
        health.probe_shelly_relay_state = original_probe
        health.time.sleep = original_sleep


def main():
    for rel in (
        "core/context.py",
        "core/hardware/shelly/api.py",
        "core/actuators.py",
        "services/actuator_health.py",
        "services/shelly.py",
        "core/release.py",
        "tests/regression/check_shelly_rpc_coordination.py",
    ):
        syntax(rel)

    release = importlib.import_module("core.release")
    require(
        release.GROWSTAR_VERSION == "3.9.4"
        and release.GROWSTAR_INTERNAL_PHASE == "4V.4",
        "Growstar meldet Version 3.9.4 / Phase 4V.4",
    )

    context_source = read("core/context.py")
    api_source = read("core/hardware/shelly/api.py")
    actuator_source = read("core/actuators.py")
    health_source = read("services/actuator_health.py")
    shelly_source = read("services/shelly.py")
    background_source = read("threads/shelly.py")

    require(
        "shelly_lock = threading.RLock()" in context_source,
        "Controllerweiter Shelly-Transport-Lock verwendet RLock",
    )
    require(
        "with ctx.shelly_lock:" in api_source,
        "ShellyAPI-RPC verwendet den zentralen Transport-Lock",
    )
    require(
        actuator_source.count("with ctx.shelly_lock:") >= 2,
        "Aktor-Schaltung und Relay-Statusprobe verwenden den Transport-Lock",
    )
    require(
        "with ctx.shelly_lock:" in shelly_source,
        "Legacy-Shelly-SET verwendet den Transport-Lock",
    )
    require(
        "with ctx.shelly_lock:" in background_source
        and "refresh_energy_state()" in background_source,
        "Bestehender Energy/Failsafe-Background bleibt unter demselben Shelly-Lock",
    )
    require(
        "ACTUATOR_PROBE_RETRIES = 1" in health_source
        and "ACTUATOR_PROBE_RETRY_DELAY_SEC = 0.25" in health_source,
        "Aktor-Health verwendet genau einen kurzen Retry",
    )
    require(
        "probe_shelly_relay_state" in health_source,
        "Aktor-Health nutzt die diagnostische read-only Relay-Probe",
    )
    require(
        "requests." not in health_source
        and "switch_shelly(" not in health_source
        and "set_device(" not in health_source
        and "?turn=" not in health_source,
        "Aktor-Health-Retry bleibt vollständig read-only",
    )

    _test_lock()
    _test_diagnostic_probe()
    _test_health_retry()

    print("✅ Phase 4V.4 Shelly-RPC-Koordination vollständig")


if __name__ == "__main__":
    main()
