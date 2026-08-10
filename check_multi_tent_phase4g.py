#!/usr/bin/env python3

import ast
import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def load_core_health():
    spec = importlib.util.spec_from_file_location(
        "phase4g_actuator_health",
        ROOT / "core/hardware/actuator_health.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_service(health_module):
    saved = dict(sys.modules)
    try:
        core_pkg = types.ModuleType("core")
        core_pkg.__path__ = []
        hw_pkg = types.ModuleType("core.hardware")
        hw_pkg.__path__ = []

        actuators = types.ModuleType("core.actuators")
        actuators.get_shelly_relay_state = lambda *args, **kwargs: None

        assignments = types.ModuleType("core.hardware_assignments")
        assignments.DEVICE_HARDWARE = {
            "heating": {"label": "Heizung", "ip_key": "IP_HEATING", "relay_key": "RELAY_HEATING"},
            "light": {"label": "Licht", "ip_key": "IP_LIGHT", "relay_key": "RELAY_LIGHT"},
        }

        runtime_mod = types.ModuleType("core.runtime")
        runtime_mod.list_runtimes = lambda: []

        sys.modules["core"] = core_pkg
        sys.modules["core.hardware"] = hw_pkg
        sys.modules["core.actuators"] = actuators
        sys.modules["core.hardware.actuator_health"] = health_module
        sys.modules["core.hardware_assignments"] = assignments
        sys.modules["core.runtime"] = runtime_mod

        spec = importlib.util.spec_from_file_location(
            "phase4g_service",
            ROOT / "services/actuator_health.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        current = {k: v for k, v in sys.modules.items() if k.startswith("phase4g_")}
        sys.modules.clear()
        sys.modules.update(saved)
        sys.modules.update(current)


def main():
    python_files = [
        "core/hardware/actuator_health.py",
        "services/actuator_health.py",
        "threads/hardware.py",
        "core/watchdog_health.py",
        "services/watchdog.py",
    ]
    for rel in python_files:
        ast.parse(read(rel), filename=rel)
    print("✅ Python-Syntax Phase 4G")

    service_src = read("services/actuator_health.py")
    thread_src = read("threads/hardware.py")
    watchdog_src = read("core/watchdog_health.py")
    watchdog_service_src = read("services/watchdog.py")
    template = read("templates/watchdog.html")

    require("get_shelly_relay_state" in service_src,
            "Aktor-Poll verwendet bestehende Shelly-Read-Logik")
    require("switch_shelly(" not in service_src and "requests.post" not in service_src and "requests.get" not in service_src,
            "Aktor-Poll enthält keinen eigenen Schalt- oder HTTP-Befehl")
    require("ThreadPoolExecutor" in service_src,
            "Mehrere Endpunkte werden begrenzt parallel geprüft")
    require("poll_assigned_actuators()" in thread_src,
            "Zentraler Hardware-Thread führt Aktor-Poll aus")
    require("get_endpoint_health" in watchdog_src and "get_shelly_relay_state" not in watchdog_src,
            "Watchdog liest nur Health-Cache und pingt keine Shellys")
    require("Aktor-Erreichbarkeit" in template and "endpoint-list" in template,
            "Watchdog zeigt zentrale Aktor-Erreichbarkeit und Endpunkte")
    require("HARDWARE_WARN_FAILURES = 2" in watchdog_service_src,
            "Watchdog warnt erst nach wiederholtem Aktorfehler")

    health = load_core_health()
    health.clear_actuator_health()

    ok = health.record_probe(
        "192.0.2.10", 0,
        reachable=True,
        actual_state=False,
        latency_ms=12.5,
        owners=[{"tent_id": "tent_1", "device": "heating"}],
        now=1000,
    )
    require(ok["reachable"] is True and ok["consecutive_failures"] == 0,
            "Erfolgreicher Probe wird gespeichert")
    snap = health.get_endpoint_health("192.0.2.10", 0, now=1010)
    require(snap["state"] == "ok" and snap["actual_state"] is False,
            "Relay-Zustand und frischer Health-State bleiben erhalten")

    failed = health.record_probe(
        "192.0.2.10", 0,
        reachable=False,
        error="timeout",
        now=1020,
    )
    failed = health.record_probe(
        "192.0.2.10", 0,
        reachable=False,
        error="timeout",
        now=1050,
    )
    require(failed["consecutive_failures"] == 2,
            "Aufeinanderfolgende Hardwarefehler werden gezählt")
    snap = health.get_endpoint_health("192.0.2.10", 0, now=1050)
    require(snap["state"] == "error" and snap["last_error"] == "timeout",
            "Letzter Aktorfehler ist im Health-Cache sichtbar")

    class Runtime:
        def __init__(self, tent_id, cfg, live, shadow):
            self.tent_id = tent_id
            self.config = cfg
            self.control_enabled = live
            self.shadow_enabled = shadow

    rt1 = Runtime("tent_1", {
        "IP_HEATING": "192.0.2.20", "RELAY_HEATING": 0,
        "IP_LIGHT": "192.0.2.20", "RELAY_LIGHT": 1,
    }, True, False)
    rt2 = Runtime("tent_2", {
        "IP_HEATING": "192.0.2.30", "RELAY_HEATING": 0,
    }, False, True)

    service = load_service(health)
    calls = []

    def fake_probe(host, relay, timeout):
        calls.append((host, relay, timeout))
        if host == "192.0.2.30":
            return {"reachable": False, "error": "offline", "actual_state": None, "latency_ms": 5}
        return {"reachable": True, "actual_state": relay == 1, "latency_ms": 4}

    result = service.poll_assigned_actuators(
        runtimes=[rt1, rt2],
        probe=fake_probe,
        timeout=0.1,
        max_workers=2,
        now=2000,
    )
    require(result["endpoints"] == 3 and len(calls) == 3,
            "Jeder eindeutig zugeordnete Host/Relay-Endpunkt wird genau einmal geprüft")
    require(result["online"] == 2 and result["offline"] == 1,
            "LIVE- und SHADOW-Hardware werden read-only getrennt bewertet")

    poll = health.actuator_poll_status(now=2001)
    require(poll["online"] == 2 and poll["offline"] == 1 and poll["age"] == 1.0,
            "Controllerweiter Aktor-Poll-Status ist für den Watchdog verfügbar")

    print("✅ Phase 4G zentrale Aktor-Gesundheit vollständig")


if __name__ == "__main__":
    main()
