#!/usr/bin/env python3
"""Phase 4R.2 – Konfliktrichtung entspricht dem tatsächlich geänderten Aktor."""

from pathlib import Path
import ast
import importlib.util
import sys
import types

ROOT = Path(__file__).resolve().parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def load_release():
    spec = importlib.util.spec_from_file_location(
        "phase4r2_release",
        ROOT / "core" / "release.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_assignments(cfg):
    old_modules = dict(sys.modules)

    core_pkg = types.ModuleType("core")
    core_pkg.__path__ = []
    sys.modules["core"] = core_pkg

    config_mod = types.ModuleType("core.config")
    config_mod.config = cfg
    config_mod.save_config = lambda value: None
    sys.modules["core.config"] = config_mod

    runtime_mod = types.ModuleType("core.runtime")
    runtime_mod.get_runtime = lambda tent_id: None
    runtime_mod.list_runtimes = lambda: []
    sys.modules["core.runtime"] = runtime_mod

    tent_config_mod = types.ModuleType("core.tent_config")
    tent_config_mod.ensure_tent_config = lambda tent_id: None
    tent_config_mod.load_tent_config = lambda tent_id: {}
    tent_config_mod.save_tent_config = lambda tent_id, value: None
    sys.modules["core.tent_config"] = tent_config_mod

    class Manager:
        def get(self, tent_id):
            if tent_id == "tent_2":
                return {
                    "id": "tent_2",
                    "name": "Zelt 2",
                    "control_enabled": False,
                    "shadow_enabled": False,
                }
            return None

        def list_tents(self):
            return [{"id": "tent_2", "name": "Zelt 2"}]

    tents_mod = types.ModuleType("core.tents")
    tents_mod.DEFAULT_TENT_ID = "tent_2"
    tents_mod.manager = Manager()
    tents_mod.validate_tent_id = lambda tent_id: str(tent_id)
    sys.modules["core.tents"] = tents_mod

    hardware_pkg = types.ModuleType("core.hardware")
    hardware_pkg.__path__ = []
    sys.modules["core.hardware"] = hardware_pkg

    health_mod = types.ModuleType("core.hardware.actuator_health")
    health_mod.get_endpoint_health = lambda host, relay: {
        "state": "ok",
        "reachable": True,
        "actual_state": False,
    }
    sys.modules["core.hardware.actuator_health"] = health_mod

    spec = importlib.util.spec_from_file_location(
        "phase4r2_assignments",
        ROOT / "core" / "hardware_assignments.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module, old_modules


def restore_modules(old_modules):
    sys.modules.clear()
    sys.modules.update(old_modules)


def expect_conflict(mod, payload):
    try:
        mod.update_hardware_assignments("tent_2", payload)
    except mod.HardwareConflictError as exc:
        return exc
    raise AssertionError("Erwartete Doppelbelegung wurde nicht blockiert")


def main():
    for rel in (
        "core/release.py",
        "core/hardware_assignments.py",
        "check_multi_tent_phase4r2.py",
    ):
        ast.parse(read(rel), filename=rel)
        print("✅ Python-Syntax", rel)

    release = load_release()
    hardware = read("core/hardware_assignments.py")

    require(
        release.GROWSTAR_VERSION == "3.6.6"
        and release.GROWSTAR_INTERNAL_PHASE == "4R.2",
        "Growstar wurde auf Version 3.6.6 / Phase 4R.2 erhöht",
    )
    require(
        "preferred_contenders" in hardware
        and "changed_devices" in hardware
        and "owner_requested and not current_requested" in hardware,
        "Konfliktrichtung wird aus tatsächlich geänderten Endpoints abgeleitet",
    )
    require(
        "_assert_assignment_change_safe" in hardware
        and "preferred_contenders" in hardware,
        "Bestehender Reassignment-Safety-Guard bleibt im Update-Pfad aktiv",
    )

    # Screenshot-Fall: Entfeuchter besitzt .89/0, Ventilator fordert .89/0 an.
    cfg = {
        "IP_DEHUMIDIFIER": "192.0.2.89",
        "RELAY_DEHUMIDIFIER": 0,
        "DEVICE_MODES": {"vent": "OFF", "dehumidifier": "OFF"},
    }
    mod, old = load_assignments(cfg)
    try:
        conflict = expect_conflict(
            mod,
            {"assignments": {"vent": {"ip": "192.0.2.89", "relay": 0}}},
        )
        require(
            conflict.owner == {"tent_id": "tent_2", "device": "dehumidifier"}
            and conflict.contender == {"tent_id": "tent_2", "device": "vent"},
            "Ventilator ist Anforderer; bestehender Entfeuchter ist Besitzer",
        )
        require(
            "IP_VENT" not in cfg and "RELAY_VENT" not in cfg,
            "Abgelehnte Ventilator-Zuordnung wird nicht gespeichert",
        )
    finally:
        restore_modules(old)

    # Gegenrichtung: Ventilator besitzt .90/0, Entfeuchter fordert .90/0 an.
    cfg = {
        "IP_VENT": "192.0.2.90",
        "RELAY_VENT": 0,
        "DEVICE_MODES": {"vent": "OFF", "dehumidifier": "OFF"},
    }
    mod, old = load_assignments(cfg)
    try:
        conflict = expect_conflict(
            mod,
            {"assignments": {"dehumidifier": {"ip": "192.0.2.90", "relay": 0}}},
        )
        require(
            conflict.owner == {"tent_id": "tent_2", "device": "vent"}
            and conflict.contender == {"tent_id": "tent_2", "device": "dehumidifier"},
            "Entfeuchter ist Anforderer; bestehender Ventilator ist Besitzer",
        )
    finally:
        restore_modules(old)

    # Identischer Endpoint desselben Geräts: weiterhin kein Selbstkonflikt.
    cfg = {
        "IP_VENT": "192.0.2.91",
        "RELAY_VENT": 0,
        "DEVICE_MODES": {"vent": "OFF"},
    }
    mod, old = load_assignments(cfg)
    try:
        result = mod.update_hardware_assignments(
            "tent_2",
            {"assignments": {"vent": {"ip": "192.0.2.91", "relay": 0}}},
        )
        require(
            result["assignments"]["vent"]["configured"] is True,
            "Identische Ventilator-Zuordnung bleibt konfliktfrei",
        )
    finally:
        restore_modules(old)

    print("✅ Phase 4R.2 Konfliktrichtung vollständig")


if __name__ == "__main__":
    main()
