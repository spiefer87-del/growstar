#!/usr/bin/env python3
"""Phase 4R.1 – Hardware-Zuordnung ohne falsche Doppelbelegung.

Hardware- und netzwerkfrei. Prüft:
- nur geänderte Karten werden vom UI gesendet,
- dieselbe bestehende Zuordnung ist kein Konflikt,
- unberührte unvollständige Zuordnungen werden nicht nebenbei zu Relay 0,
- echte Doppelbelegung bleibt gesperrt,
- Konfliktantwort nennt Besitzer + kollidierenden Aktor.
"""

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
        "phase4r1_release",
        ROOT / "core" / "release.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def static_checks():
    for rel in (
        "core/release.py",
        "core/hardware_assignments.py",
        "routes/tents.py",
        "check_multi_tent_phase4r1.py",
    ):
        ast.parse(read(rel), filename=rel)
        print("✅ Python-Syntax", rel)

    release = load_release()
    hardware = read("core/hardware_assignments.py")
    routes = read("routes/tents.py")
    connections = read("templates/connections.html")

    history = release.release_history()
    phase4r1_release = next(
        (
            item
            for item in history
            if item.get("version") == "3.6.5"
            and item.get("phase") == "4R.1"
        ),
        None,
    )

    require(
        phase4r1_release is not None,
        "Phase 4R.1 bleibt als Version 3.6.5 in der Release-Historie erhalten",
    )

    require(
        "function assignmentChanged(currentAssignment, requested)" in connections
        and "Object.keys(assignments).length === 0" in connections,
        "Verbindungen erkennt echte Änderungen und sendet bei No-op keinen POST",
    )
    require(
        "if(assignmentChanged(currentAssignment, requested))" in connections
        and "assignments[device] = requested" in connections,
        "Nur tatsächlich geänderte Aktor-Zuordnungen werden gesendet",
    )
    require(
        "assignments[device] = {" not in connections[
            connections.index('saveButton?.addEventListener("click"') :
            connections.index("async function init()")
        ],
        "Save-Pfad kopiert nicht mehr pauschal den kompletten Snapshot",
    )
    require(
        "contender=None" in hardware
        and "self.contender = contender" in hardware
        and (
            "contender=current" in hardware
            or "contender=conflict_contender" in hardware
        ),
        "Backend-Konflikt enthält den kollidierenden Aktor",
    )
    require(
        "contender=exc.contender" in routes,
        "Hardware-API liefert den kollidierenden Aktor strukturiert zurück",
    )
    require(
        "highlightConflict(data.contender)" in connections
        and "ownerText" in connections
        and "contenderText" in connections,
        "UI zeigt Besitzer und kollidierenden Aktor und hebt die Karte hervor",
    )
    require(
        'owner != current' in hardware,
        "Dieselbe bestehende Eigentümer-Zuordnung bleibt ausdrücklich konfliktfrei",
    )
    require(
        "_assert_assignment_change_safe" in hardware
        and "_endpoint_owners(" in hardware
        and "candidate_cfg=working" in hardware,
        "Phase-4L Safety-Guard und globaler Doppelbelegungsschutz bleiben aktiv",
    )


def dynamic_assignment_checks():
    old_modules = dict(sys.modules)

    try:
        # Minimale Core-Pakete faken.
        core_pkg = types.ModuleType("core")
        core_pkg.__path__ = []
        sys.modules["core"] = core_pkg

        cfg = {
            # Zwei alte, noch unvollständige IP-Einträge ohne Relay.
            # Genau so darf ein UI-Save nicht beide nebenbei auf Relay 0 ziehen.
            "IP_VENT": "192.0.2.89",
            "IP_AUX1": "192.0.2.89",
            "DEVICE_MODES": {
                "vent": "OFF",
                "aux1": "OFF",
            },
        }
        save_calls = []

        config_mod = types.ModuleType("core.config")
        config_mod.config = cfg
        config_mod.save_config = lambda value: save_calls.append(dict(value))
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
            "phase4r1_assignments",
            ROOT / "core" / "hardware_assignments.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Nur Ventilator wird geändert/komplettiert. aux1 bleibt unberührt
        # und darf NICHT automatisch Relay 0 erhalten.
        result = mod.update_hardware_assignments(
            "tent_2",
            {
                "assignments": {
                    "vent": {
                        "ip": "192.0.2.89",
                        "relay": 0,
                    }
                }
            },
        )

        require(
            cfg.get("RELAY_VENT") == 0
            and "RELAY_AUX1" not in cfg
            and result["assignments"]["vent"]["configured"] is True
            and result["assignments"]["aux1"]["configured"] is False,
            "Partial-Patch komplettiert nur Ventilator; unberührtes aux1 bleibt offen",
        )

        # Identische Ventilator-Zuordnung erneut schreiben: kein Selbstkonflikt.
        mod.update_hardware_assignments(
            "tent_2",
            {
                "assignments": {
                    "vent": {
                        "ip": "192.0.2.89",
                        "relay": 0,
                    }
                }
            },
        )
        print("✅ Identische Ventilator-Zuordnung verursacht keinen Selbstkonflikt")

        # Nun aux1 bewusst auf denselben echten Endpoint legen -> muss blocken.
        try:
            mod.update_hardware_assignments(
                "tent_2",
                {
                    "assignments": {
                        "aux1": {
                            "ip": "192.0.2.89",
                            "relay": 0,
                        }
                    }
                },
            )
        except mod.HardwareConflictError as exc:
            conflict = exc
        else:
            conflict = None

        require(
            conflict is not None,
            "Echte Doppelbelegung desselben IP/Relay-Endpunkts bleibt gesperrt",
        )
        require(
            conflict.owner == {"tent_id": "tent_2", "device": "vent"}
            and conflict.contender == {"tent_id": "tent_2", "device": "aux1"},
            "Konflikt benennt bestehenden Besitzer und kollidierenden Aktor eindeutig",
        )
        require(
            cfg.get("RELAY_AUX1") is None,
            "Abgelehnter Konflikt wird nicht in die Config geschrieben",
        )

    finally:
        sys.modules.clear()
        sys.modules.update(old_modules)


def main():
    static_checks()
    dynamic_assignment_checks()
    print("✅ Phase 4R.1 Hardware-Zuordnungs-Fix vollständig")


if __name__ == "__main__":
    main()
