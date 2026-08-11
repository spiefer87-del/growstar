#!/usr/bin/env python3
"""Growstar Phase 4I – stationsbezogener Safety-Supervisor.

Der Test sendet keine Netzwerkbefehle. Hardware-Health und Shelly-Schaltungen
werden vollstaendig durch isolierte Stubs ersetzt.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
import time
import types
from types import SimpleNamespace

try:
    from jinja2 import Environment
except ModuleNotFoundError:
    Environment = None


ROOT = Path(__file__).resolve().parent


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def static_checks():
    runtime = read("core/runtime.py")
    actuators = read("core/actuators.py")
    safety = read("core/safety.py")
    service = read("services/safety.py")
    shelly_thread = read("threads/shelly.py")
    watchdog = read("core/watchdog_health.py")
    template = read("templates/watchdog.html")

    for name, source in (
        ("core/runtime.py", runtime),
        ("core/actuators.py", actuators),
        ("core/safety.py", safety),
        ("services/safety.py", service),
        ("threads/shelly.py", shelly_thread),
        ("core/watchdog_health.py", watchdog),
        ("check_multi_tent_phase4i.py", read("check_multi_tent_phase4i.py")),
    ):
        ast.parse(source, filename=name)

    if Environment is not None:
        Environment().parse(template)

    check(
        "safety_overrides" in runtime
        and "safety_status" in runtime
        and "safety_lock" in runtime,
        "Runtime besitzt isolierten Safety-State pro Station",
    )
    check(
        "safety_overrides" in actuators
        and 'override.get("force_off")' in actuators
        and 'override.get("block_on")' in actuators,
        "Aktorpfad besitzt harte Safety-Barriere vor realen Shelly-Befehlen",
    )
    check(
        "requests." not in safety
        and "switch_shelly" not in safety,
        "Safety-Bewertung ist read-only und sendet keine eigenen Netzwerk-Pings",
    )
    check(
        "SAFETY_LOOP_MAX_AGE_SEC" in safety
        and "SENSOR_TIMEOUT" in safety,
        "Safety bewertet Regelkreis-Heartbeat und bestehende Sensor-Freshness",
    )
    check(
        "run_all_live_safety" in shelly_thread
        and "SAFETY_INTERVAL = 2" in shelly_thread,
        "Unabhaengiger Shelly-Thread fuehrt Safety alle 2 Sekunden aus",
    )
    check(
        "get_runtime_safety_snapshot" in watchdog
        and '"safety": safety' in watchdog,
        "Watchdog liefert stationsbezogenen Safety-Status",
    )
    check(
        "SUPERVISOR STALE" in template
        and "FAILSAFE" in template
        and "<span>Safety</span>" in template,
        "Watchdog-Oberflaeche zeigt Safety und Supervisor-Heartbeat",
    )


def load_safety_module():
    # ----- Stub-Paket core -----
    core = types.ModuleType("core")
    core.__path__ = []
    sys.modules["core"] = core

    constants = types.ModuleType("core.constants")
    constants.SENSOR_TIMEOUT = 120
    sys.modules["core.constants"] = constants

    device_names = (
        "heating", "fan", "light", "vent", "irrigation",
        "humidifier", "dehumidifier", "light2", "vent2",
    )
    devices = types.ModuleType("core.devices")
    devices.DEVICE_NAMES = device_names

    def get_device_mode(device, runtime=None):
        value = (runtime.config.get("DEVICE_MODES") or {}).get(device, "OFF")
        if isinstance(value, dict):
            value = value.get("mode", "OFF")
        return str(value or "OFF").upper()

    devices.get_device_mode = get_device_mode
    sys.modules["core.devices"] = devices

    hardware_pkg = types.ModuleType("core.hardware")
    hardware_pkg.__path__ = []
    sys.modules["core.hardware"] = hardware_pkg

    health = types.ModuleType("core.hardware.actuator_health")
    health.health_map = {}

    def get_endpoint_health(host, relay, now=None):
        value = health.health_map.get((str(host), int(relay)))
        return None if value is None else dict(value)

    health.get_endpoint_health = get_endpoint_health
    sys.modules["core.hardware.actuator_health"] = health

    assignments = types.ModuleType("core.hardware_assignments")
    assignments.DEVICE_HARDWARE = {
        device: {
            "label": device,
            "ip_key": "IP_" + device.upper(),
            "relay_key": "RELAY_" + device.upper(),
        }
        for device in device_names
    }
    sys.modules["core.hardware_assignments"] = assignments

    runtime_module = types.ModuleType("core.runtime")
    runtime_module.resolve_runtime = lambda runtime=None: runtime
    sys.modules["core.runtime"] = runtime_module

    spec = importlib.util.spec_from_file_location(
        "phase4i_core_safety",
        ROOT / "core/safety.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, health


def runtime_fixture(tent_id="tent_test", *, now=None):
    now = time.time() if now is None else float(now)
    state = SimpleNamespace(
        live_state={
            "temp": 22.0,
            "hum": 55.0,
            "heating": False,
            "fan": False,
            "light": False,
            "vent": False,
            "irrigation": False,
            "humidifier": False,
            "dehumidifier": False,
            "light2": False,
            "vent2": False,
        },
        last_ds_time=now - 1,
        last_dht_time=now - 1,
        temp_stale=False,
        hum_stale=False,
        heating_on=False,
        fan_on=False,
        light_on=False,
        vent_on=False,
        irrigation_on=False,
        humidifier_on=False,
        dehumidifier_on=False,
        light2_on=False,
        vent2_on=False,
    )
    config = {
        "SENSOR_ASSIGNMENTS": {
            "temperature": {"source_id": f"mqtt:{tent_id}_temp"},
            "humidity": {"source_id": f"mqtt:{tent_id}_hum"},
        },
        "DEVICE_MODES": {
            "heating": "ENV",
            "light": "TIME",
            "fan": "OFF",
            "vent": "OFF",
            "irrigation": "OFF",
            "humidifier": "OFF",
            "dehumidifier": "OFF",
            "light2": "OFF",
            "vent2": "OFF",
        },
        "DEVICE_ENV_CONFIG": {},
        "IP_HEATING": f"10.0.0.{10 if tent_id == 'tent_a' else 20}",
        "RELAY_HEATING": 0,
        "IP_LIGHT": f"10.0.1.{10 if tent_id == 'tent_a' else 20}",
        "RELAY_LIGHT": 0,
    }
    return SimpleNamespace(
        tent_id=tent_id,
        name=tent_id,
        state=state,
        config=config,
        enabled=True,
        control_enabled=True,
        disarming=False,
        last_loop_ts=now - 1,
        safety_overrides={},
        safety_status=None,
        last_safety_ts=None,
        safety_lock=None,
    )


def ok_health(actual=False):
    return {
        "state": "ok",
        "reachable": True,
        "actual_state": bool(actual),
        "check_age": 1.0,
        "success_age": 1.0,
        "last_error": None,
    }


def pure_safety_checks():
    module, health = load_safety_module()
    now = 10_000.0
    rt = runtime_fixture("tent_a", now=now)

    health.health_map[(rt.config["IP_HEATING"], 0)] = ok_health(False)
    health.health_map[(rt.config["IP_LIGHT"], 0)] = ok_health(False)

    snap = module.evaluate_runtime_safety(rt, now=now)
    check(not snap["active"], "Gesunde LIVE-Station bleibt Safety NORMAL")

    rt.state.temp_stale = True
    rt.state.live_state["temp"] = None
    snap = module.evaluate_runtime_safety(rt, now=now)
    check(
        snap["overrides"]["heating"]["force_off"] is True,
        "Stale Temperatur erzwingt Heizung SAFE AUS",
    )
    check(
        "light" not in snap["overrides"],
        "Stale Temperatur beeinflusst zeitgesteuertes Licht nicht",
    )

    rt.state.temp_stale = False
    rt.state.live_state["temp"] = 22.0
    rt.state.last_ds_time = now - 1
    rt.config["DEVICE_MODES"]["humidifier"] = "ENV"
    rt.config["DEVICE_ENV_CONFIG"]["humidifier"] = {
        "use_temp": False,
        "use_hum": True,
    }
    rt.config["IP_HUMIDIFIER"] = "10.0.2.10"
    rt.config["RELAY_HUMIDIFIER"] = 0
    health.health_map[("10.0.2.10", 0)] = ok_health(False)
    rt.state.hum_stale = True
    rt.state.live_state["hum"] = None

    snap = module.evaluate_runtime_safety(rt, now=now)
    check(
        snap["overrides"]["humidifier"]["force_off"] is True,
        "Stale Feuchte erzwingt feuchteabhaengigen Aktor SAFE AUS",
    )
    check(
        "heating" not in snap["overrides"],
        "Stale Feuchte beeinflusst temperaturabhaengige Heizung nicht",
    )

    # Loop-Stale gilt fuer alle aktiv geregelten Aktoren, auch TIME/ON.
    rt.state.hum_stale = False
    rt.state.live_state["hum"] = 55.0
    rt.state.last_dht_time = now - 1
    rt.last_loop_ts = now - 30
    snap = module.evaluate_runtime_safety(rt, now=now)
    check(
        snap["overrides"]["heating"]["force_off"]
        and snap["overrides"]["light"]["force_off"],
        "Haengender Regelkreis erzwingt alle aktiven Geraete SAFE AUS",
    )

    # Hardwarefehler blockiert nur den betroffenen Aktor; kein Blind-Ping.
    rt.last_loop_ts = now - 1
    health.health_map[(rt.config["IP_HEATING"], 0)] = {
        "state": "error",
        "reachable": False,
        "actual_state": None,
        "last_error": "timeout",
    }
    snap = module.evaluate_runtime_safety(rt, now=now)
    check(
        snap["overrides"]["heating"]["block_on"] is True
        and snap["overrides"]["heating"]["force_off"] is False,
        "Offline-Heizung blockiert neue EIN-Befehle ohne falsche Safe-Off-Bestaetigung",
    )
    check(
        "light" not in snap["overrides"],
        "Aktorfehler bleibt auf den betroffenen Endpunkt begrenzt",
    )

    # Recovery loest den Override automatisch.
    health.health_map[(rt.config["IP_HEATING"], 0)] = ok_health(False)
    snap = module.evaluate_runtime_safety(rt, now=now)
    check(
        "heating" not in snap["overrides"],
        "Gesunder Sensor/Loop/Endpunkt hebt Safety-Override automatisch auf",
    )

    rt.control_enabled = False
    snap = module.evaluate_runtime_safety(rt, now=now)
    check(
        snap["state"] == "inactive" and not snap["overrides"],
        "SHADOW/ARMING sendet keine LIVE-Safety-Aktorik",
    )


def actuator_gate_checks():
    # Isolierte Imports fuer core.actuators.
    for key in ["core", "core.runtime"]:
        sys.modules.pop(key, None)

    core = types.ModuleType("core")
    core.__path__ = []
    sys.modules["core"] = core
    runtime_module = types.ModuleType("core.runtime")
    runtime_module.resolve_runtime = lambda runtime=None: runtime
    sys.modules["core.runtime"] = runtime_module

    # requests muss beim Import vorhanden sein, wird aber nicht wirklich benutzt.
    requests = types.ModuleType("requests")
    requests.post = lambda *a, **k: None
    requests.get = lambda *a, **k: None
    sys.modules["requests"] = requests

    spec = importlib.util.spec_from_file_location(
        "phase4i_actuators",
        ROOT / "core/actuators.py",
    )
    actuator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(actuator)

    now = time.time()
    rt = runtime_fixture("tent_a", now=now)
    rt.safety_overrides = {
        "heating": {
            "force_off": True,
            "block_on": True,
            "can_attempt_off": True,
            "reason": "Temperatursensor stale",
        }
    }
    calls = []
    actuator.switch_shelly = lambda ip, relay, enabled, timeout=3: calls.append(
        (ip, int(relay), bool(enabled))
    ) or True

    # Bereits AUS: ON-Anforderung darf keinen Netzwerkbefehl erzeugen.
    actuator.set_heating(True, runtime=rt)
    check(not calls, "Hard-Gate unterdrueckt unsafe EIN direkt im Aktorpfad")

    # Bereits EIN: derselbe ON-Wunsch wird unter Safety zu realem AUS.
    rt.state.heating_on = True
    rt.state.live_state["heating"] = True
    actuator.set_heating(True, runtime=rt)
    check(
        calls and calls[-1][2] is False
        and rt.state.heating_on is False,
        "Hard-Gate verwandelt unsafe EIN bei laufendem Aktor in SAFE AUS",
    )

    calls.clear()
    rt.safety_overrides = {
        "heating": {
            "force_off": False,
            "block_on": True,
            "can_attempt_off": False,
            "reason": "Hardware offline",
        }
    }
    actuator.set_heating(True, runtime=rt)
    check(
        not calls,
        "Unverifizierte Hardware erzeugt keinen neuen EIN-Netzwerkbefehl",
    )


def service_isolation_checks():
    # Core-Safety frisch isoliert laden.
    for key in list(sys.modules):
        if key == "core" or key.startswith("core.") or key == "services" or key.startswith("services."):
            sys.modules.pop(key, None)

    safety, health = load_safety_module()
    now = 20_000.0
    a = runtime_fixture("tent_a", now=now)
    b = runtime_fixture("tent_b", now=now)

    for rt in (a, b):
        health.health_map[(rt.config["IP_HEATING"], 0)] = ok_health(False)
        health.health_map[(rt.config["IP_LIGHT"], 0)] = ok_health(False)

    b.state.temp_stale = True
    b.state.live_state["temp"] = None
    b.state.heating_on = True
    b.state.live_state["heating"] = True

    core_act = types.ModuleType("core.actuators")
    calls = []

    def set_device(device, enabled, runtime=None, reason=""):
        calls.append((runtime.tent_id, device, bool(enabled), reason))
        setattr(runtime.state, f"{device}_on", bool(enabled))
        runtime.state.live_state[device] = bool(enabled)

    core_act.set_device = set_device
    sys.modules["core.actuators"] = core_act

    runtime_module = sys.modules["core.runtime"]
    runtime_module.list_runtimes = lambda: [a, b]
    runtime_module.resolve_runtime = lambda runtime=None: runtime

    sys.modules["core.safety"] = safety

    services_pkg = types.ModuleType("services")
    services_pkg.__path__ = []
    sys.modules["services"] = services_pkg

    spec = importlib.util.spec_from_file_location(
        "services.safety",
        ROOT / "services/safety.py",
    )
    service = importlib.util.module_from_spec(spec)
    sys.modules["services.safety"] = service
    spec.loader.exec_module(service)

    result = service.run_all_live_safety(now=now, enforce=True)
    check(
        result["tent_a"]["active"] is False,
        "Gesunde Station bleibt bei Fehler einer anderen Station unangetastet",
    )
    check(
        any(call[0] == "tent_b" and call[1] == "heating" and call[2] is False for call in calls)
        and not any(call[0] == "tent_a" for call in calls),
        "Safety-Off wird ausschliesslich in der betroffenen Station ausgefuehrt",
    )

    # Selbst ein interner Bewertungsfehler einer LIVE-Station muss fail-closed
    # bleiben und darf die gesunde Nachbarstation nicht mitreissen.
    original_evaluate = service.evaluate_runtime_safety
    calls.clear()
    b.state.temp_stale = False
    b.state.live_state["temp"] = 22.0
    b.state.last_ds_time = now - 1
    b.state.heating_on = True
    b.state.live_state["heating"] = True

    def raising_evaluate(runtime, now=None):
        if runtime.tent_id == "tent_b":
            raise RuntimeError("synthetischer Safety-Testfehler")
        return original_evaluate(runtime, now=now)

    service.evaluate_runtime_safety = raising_evaluate
    try:
        failed = service.run_all_live_safety(now=now, enforce=True)
    finally:
        service.evaluate_runtime_safety = original_evaluate

    check(
        failed["tent_b"]["active"] is True
        and failed["tent_b"]["overrides"].get("heating", {}).get("force_off") is True,
        "Interner Safety-Fehler faellt betroffene LIVE-Station fail-closed",
    )
    check(
        failed["tent_a"]["active"] is False,
        "Safety-Auswertungsfehler einer Station beeinflusst keine andere Runtime",
    )


def main():
    static_checks()
    pure_safety_checks()
    actuator_gate_checks()
    service_isolation_checks()
    print("✅ Phase 4I stationsbezogener Safety-Supervisor vollstaendig")


if __name__ == "__main__":
    main()
