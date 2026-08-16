#!/usr/bin/env python3
"""Growstar Phase 4L – Device Guard / Hardware Truth / Safety UI.

Der Test ist hardware- und netzwerkfrei. Er prüft nur Quellcode und isolierte
Guard-Funktionen gegen Fakes. Es werden keine Shelly-Befehle gesendet.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import types
from pathlib import Path

try:
    from jinja2 import Environment
except ModuleNotFoundError:
    Environment = None


ROOT = Path(__file__).resolve().parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def syntax_checks():
    for rel in (
        "core/devices.py",
        "core/hardware_assignments.py",
        "routes/device.py",
        "routes/tents.py",
        "check_multi_tent_phase4l.py",
    ):
        ast.parse(read(rel), filename=rel)
    print("✅ Python-Syntax Phase 4L")

    if Environment is not None:
        env = Environment()
        for rel in (
            "templates/device_control.html",
            "templates/connections.html",
            "templates/grow_control.html",
        ):
            env.parse(read(rel))
        print("✅ Jinja-Syntax Phase 4L")


def static_checks():
    devices = read("core/devices.py")
    hardware = read("core/hardware_assignments.py")
    route_device = read("routes/device.py")
    routes_tents = read("routes/tents.py")
    detail = read("templates/device_control.html")
    connections = read("templates/connections.html")
    dashboard = read("templates/grow_control.html")

    require(
        "DeviceHardwareRequiredError" in devices
        and "_assert_hardware_for_active_mode" in devices,
        "Backend besitzt harten Guard für aktive Modi ohne Hardware",
    )
    require(
        'if mode == "OFF":' in devices,
        "OFF bleibt ohne Hardware als sicherer Rückweg erlaubt",
    )
    require(
        "device_hardware_required" in route_device,
        "Geräte-API liefert strukturierten Hardware-Hinweis",
    )
    require(
        "HardwareAssignmentActiveModeError" in hardware,
        "Endpoint-Änderung bei aktivem Gerätemodus wird blockiert",
    )
    require(
        "HardwareAssignmentNotSafeOffError" in hardware
        and 'health.get("state") == "ok"' in hardware
        and 'health.get("actual_state") is False' in hardware,
        "LIVE-Endpoint darf erst nach bestätigtem ONLINE · AUS geändert werden",
    )
    require(
        "switch_shelly" not in hardware,
        "Zuordnungs-Guard selbst sendet keine Relay-Befehle",
    )
    require(
        '"physical_known"' in routes_tents
        and '"physical_on"' in routes_tents
        and "get_endpoint_health" in routes_tents,
        "Stations-State liefert zentral verifizierten physischen Relay-Zustand",
    )
    require(
        '"safety"' in routes_tents
        and '"blocked_devices"' in routes_tents
        and "get_runtime_safety_snapshot" in routes_tents,
        "Stations-State liefert Phase-4I-Safety an normales Dashboard",
    )
    require(
        "option.disabled = option.value !== \"OFF\"" in detail
        and "NICHT ZUGEORDNET" in detail,
        "Gerätedetail sperrt aktive Modi ohne Zuordnung",
    )
    require(
        "modeLocked" in connections
        and "Gerät zuerst auf Deaktiviert / OFF setzen" in connections,
        "Verbindungen sperren Endpoint-Felder bei aktivem Modus",
    )
    require(
        "hardware_assignment_active_mode" in routes_tents
        and "hardware_assignment_not_safe_off" in routes_tents,
        "Hardware-API liefert beide neuen Guard-Fehler strukturiert",
    )
    require(
        "NICHT ZUGEORDNET" in dashboard
        and "device.physical_known" in dashboard
        and "device.physical_on" in dashboard,
        "Dashboard priorisiert Hardware-Wahrheit vor altem Runtime-Bool",
    )
    require(
        "SAFE AUS" in dashboard
        and "SAFETY FAILSAFE AKTIV" in dashboard,
        "Failsafe ist im normalen Zelt-Dashboard deutlich sichtbar",
    )


def dynamic_device_mode_guard():
    """core.devices isoliert testen."""

    old_modules = dict(sys.modules)
    try:
        core_pkg = types.ModuleType("core")
        core_pkg.__path__ = []
        sys.modules["core"] = core_pkg

        runtime_mod = types.ModuleType("core.runtime")

        class Runtime:
            tent_id = "tent_test"

            def __init__(self):
                self.config = {
                    "DEVICE_MODES": {"vent": "OFF"},
                    "DEVICE_PARAMS": {},
                    "DEVICE_ENV_CONFIG": {},
                }
                self.persist_count = 0

            def persist_config(self):
                self.persist_count += 1

        runtime = Runtime()
        runtime_mod.resolve_runtime = lambda value=None: value or runtime
        sys.modules["core.runtime"] = runtime_mod

        assignment = {"configured": False, "ip": "", "relay": None}
        hardware_mod = types.ModuleType("core.hardware_assignments")
        hardware_mod.device_assignment = (
            lambda tent_id, device: dict(assignment)
        )
        sys.modules["core.hardware_assignments"] = hardware_mod

        spec = importlib.util.spec_from_file_location(
            "phase4l_devices",
            ROOT / "core" / "devices.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        before = dict(runtime.config["DEVICE_MODES"])
        try:
            mod.update_device_config(
                "vent",
                {"mode": "ON"},
                runtime=runtime,
            )
        except mod.DeviceHardwareRequiredError:
            blocked = True
        else:
            blocked = False

        require(
            blocked
            and runtime.config["DEVICE_MODES"] == before
            and runtime.persist_count == 0,
            "ON ohne Hardware wird atomar abgelehnt",
        )

        mod.update_device_config(
            "vent",
            {"mode": "OFF"},
            runtime=runtime,
        )
        require(
            runtime.config["DEVICE_MODES"]["vent"] == "OFF"
            and runtime.persist_count == 1,
            "OFF ohne Hardware wird weiterhin gespeichert",
        )

        assignment.update({
            "configured": True,
            "ip": "192.0.2.10",
            "relay": 0,
        })
        mod.update_device_config(
            "vent",
            {"mode": "ENV"},
            runtime=runtime,
        )
        require(
            runtime.config["DEVICE_MODES"]["vent"] == "ENV"
            and runtime.persist_count == 2,
            "Aktiver Modus mit vollständiger Zuordnung bleibt erlaubt",
        )

    finally:
        sys.modules.clear()
        sys.modules.update(old_modules)


def dynamic_assignment_guard():
    """core.hardware_assignments isoliert testen."""

    old_modules = dict(sys.modules)
    try:
        core_pkg = types.ModuleType("core")
        core_pkg.__path__ = []
        sys.modules["core"] = core_pkg

        config_mod = types.ModuleType("core.config")
        config_mod.config = {}
        config_mod.save_config = lambda cfg: None
        sys.modules["core.config"] = config_mod

        runtime_mod = types.ModuleType("core.runtime")
        runtime_mod.get_runtime = lambda tent_id: None
        runtime_mod.list_runtimes = lambda: []
        sys.modules["core.runtime"] = runtime_mod

        tent_config_mod = types.ModuleType("core.tent_config")
        tent_config_mod.ensure_tent_config = lambda tent_id: None
        tent_config_mod.load_tent_config = lambda tent_id: {}
        tent_config_mod.save_tent_config = lambda tent_id, cfg: None
        sys.modules["core.tent_config"] = tent_config_mod

        class Manager:
            def get(self, tent_id):
                return {"id": tent_id, "name": tent_id}
            def list_tents(self):
                return []

        tents_mod = types.ModuleType("core.tents")
        tents_mod.DEFAULT_TENT_ID = "tent_1"
        tents_mod.manager = Manager()
        tents_mod.validate_tent_id = lambda tent_id: str(tent_id)
        sys.modules["core.tents"] = tents_mod

        health_result = {
            "state": "ok",
            "reachable": True,
            "actual_state": False,
        }
        hardware_pkg = types.ModuleType("core.hardware")
        hardware_pkg.__path__ = []
        sys.modules["core.hardware"] = hardware_pkg

        health_mod = types.ModuleType("core.hardware.actuator_health")
        health_mod.get_endpoint_health = (
            lambda host, relay: dict(health_result)
        )
        sys.modules["core.hardware.actuator_health"] = health_mod

        spec = importlib.util.spec_from_file_location(
            "phase4l_assignments",
            ROOT / "core" / "hardware_assignments.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        class Runtime:
            tent_id = "tent_test"
            control_enabled = True

        runtime = Runtime()
        current = {
            "assignments": {
                "vent": {
                    "device": "vent",
                    "ip": "192.0.2.10",
                    "relay": 0,
                    "configured": True,
                    "mode": "ON",
                }
            }
        }

        try:
            mod._assert_assignment_change_safe(
                "tent_test",
                runtime,
                current,
                {"vent": ("192.0.2.11", 0)},
            )
        except mod.HardwareAssignmentActiveModeError:
            blocked = True
        else:
            blocked = False
        require(
            blocked,
            "Aktiver Modus verhindert Endpoint-Wechsel auch backendseitig",
        )

        # Unveränderte Zuordnung muss erlaubt bleiben, weil das Connections-UI
        # den kompletten Snapshot zurückschickt.
        mod._assert_assignment_change_safe(
            "tent_test",
            runtime,
            current,
            {"vent": ("192.0.2.10", 0)},
        )
        print("✅ Unveränderte aktive Zuordnung bleibt zulässig")

        current["assignments"]["vent"]["mode"] = "OFF"
        health_result["actual_state"] = True
        try:
            mod._assert_assignment_change_safe(
                "tent_test",
                runtime,
                current,
                {"vent": None},
            )
        except mod.HardwareAssignmentNotSafeOffError:
            safe_off_blocked = True
        else:
            safe_off_blocked = False

        require(
            safe_off_blocked,
            "LIVE-Endpunkt bleibt gesperrt solange Hardware EIN bestätigt",
        )

        health_result["actual_state"] = False
        mod._assert_assignment_change_safe(
            "tent_test",
            runtime,
            current,
            {"vent": None},
        )
        print("✅ LIVE-Endpunkt darf nach bestätigtem ONLINE · AUS freigegeben werden")

    finally:
        sys.modules.clear()
        sys.modules.update(old_modules)


def main():
    syntax_checks()
    static_checks()
    dynamic_device_mode_guard()
    dynamic_assignment_guard()
    print("✅ Phase 4L Geräte-Guard / Hardware-Truth / Safety-UI vollständig")


if __name__ == "__main__":
    main()
