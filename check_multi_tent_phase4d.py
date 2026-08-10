#!/usr/bin/env python3
"""Phase 4D: Setup und sichere Hardware-Zuordnung pro lokaler Station."""

import ast
import importlib.util
import os
from pathlib import Path
import tempfile

from jinja2 import Environment

ROOT = Path(__file__).parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    python_files = [
        "core/tents.py",
        "core/hardware_assignments.py",
        "routes/tents.py",
        "routes/dashboard.py",
        "auth/policy.py",
    ]
    templates = [
        "templates/grow_control.html",
        "templates/grow_control_dashboard.html",
        "templates/grow_control_setup.html",
        "templates/connections.html",
    ]

    for rel in python_files:
        ast.parse(read(rel), filename=rel)

    env = Environment()
    for rel in templates:
        env.parse(read(rel))

    routes = read("routes/dashboard.py")
    tent_routes = read("routes/tents.py")
    tents_core = read("core/tents.py")
    hardware_core = read("core/hardware_assignments.py")
    hub = read("templates/grow_control_dashboard.html")
    grow = read("templates/grow_control.html")
    setup = read("templates/grow_control_setup.html")
    connections = read("templates/connections.html")

    checks = {
        "Sensoren-Button oben rechts entfernt": "tool-link" not in grow and ">🧪 Sensoren<" not in grow,
        "Grow-Control Setup-Route vorhanden": '/grow-control/setup' in routes and 'grow_control_setup.html' in routes,
        "Grow-Control Connections-Route vorhanden": '/grow-control/connections' in routes and 'render_template("connections.html")' in routes,
        "Legacy /connections leitet auf zentrale Seite": 'def connections_page()' in routes and 'grow_control_connections' in routes,
        "Hub Setup zeigt auf neues Setup": "url_for('grow_control_setup')" in hub,
        "Hub Verbindungen zeigt auf zentrale Zuordnung": "url_for('grow_control_connections')" in hub,
        "Setup listet Stationen dynamisch": 'fetch(API)' in setup and '"/api/tents"' in setup,
        "Setup kann neue Station anlegen": 'method:"POST"' in setup and 'tent_id:id' in setup,
        "Setup kann Stationsmetadaten ändern": 'method:"PATCH"' in setup,
        "Stationsmetadaten werden atomar aktualisiert": 'def update_tent(' in tents_core and 'Erst nach vollständiger Validierung' in tents_core,
        "Tent API unterstützt Anlegen": '@app.route("/api/tents", methods=["GET", "POST"])' in tent_routes,
        "Tent API unterstützt Metadaten-Patch": '@app.route("/api/tents/<tent_id>", methods=["GET", "PATCH"])' in tent_routes,
        "Hardware API pro Station vorhanden": '/api/tents/<tent_id>/hardware' in tent_routes,
        "Connections nutzt nur stationsbezogene Hardware-API": '/api/tents/${encodeURIComponent(id)}/hardware' in connections and '/api/config' not in connections and '/api/state' not in connections,
        "IP und Relay bleiben manuell zuweisbar": 'IP / Host' in connections and 'Relay' in connections,
        "Alle bekannten Aktoren sind zentral definiert": all(name in hardware_core for name in ('heating','fan','light','vent','irrigation','humidifier','dehumidifier','light2','vent2')),
        "Doppelbelegung IP+Relay wird geprüft": 'HardwareConflictError' in hardware_core and '_endpoint_owners' in hardware_core,
        "LIVE-Zuordnung ist bearbeitbar": '"editable": True' in hardware_core and 'Hardware-Zuordnung einer LIVE-Station ist in Phase 4D gesperrt' not in hardware_core,
        "Nicht verwendete Aktoren dürfen offen bleiben": 'if not host:' in hardware_core and 'normalized[device] = None' in hardware_core,
        "Relay 0 ist Standard bei gesetzter IP": 'if relay is None:' in hardware_core and 'relay = 0' in hardware_core,
        "Shadow-Zuordnung schaltet keine Hardware": 'switch_shelly' not in hardware_core,
        "Connections erlaubt LIVE-Bearbeitung": 'LIVE. Hardware-Zuordnungen sind bearbeitbar' in connections and 'schreibgeschützt' not in connections,
        "Connections ignoriert Relay bei leerer IP": 'relay: ip ? relay : ""' in connections,
        "Offene Aktoren zeigen Relay-Strich statt 0": 'const hasSelection = selected !== null' in connections and 'hasSelection && Number(selected)===i' in connections,
    }

    spec = importlib.util.spec_from_file_location("phase4d_policy", ROOT / "auth" / "policy.py")
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)

    req = policy.permission_requirement("/grow-control/connections", "GET")
    checks["Connections benötigt hardware.view"] = req.allows({"hardware.view"}) and not req.allows({"grow.view"})

    req = policy.permission_requirement("/api/tents/tent_2/hardware", "GET")
    checks["Hardware-Zuordnung lesen benötigt hardware.view"] = req.allows({"hardware.view"}) and not req.allows({"grow.view"})

    req = policy.permission_requirement("/api/tents/tent_2/hardware", "POST")
    checks["Hardware-Zuordnung schreiben benötigt hardware.configure"] = req.allows({"hardware.configure"}) and not req.allows({"grow.configure"})

    req = policy.permission_requirement("/api/tents", "POST")
    checks["Station anlegen benötigt grow.configure"] = req.allows({"grow.configure"}) and not req.allows({"grow.control"})

    # Dynamischer Konflikt-/Persistenztest ohne echte Hardware.
    from core.hardware_assignments import HardwareConflictError, hardware_snapshot, update_hardware_assignments
    from core.tent_config import ensure_tent_config
    from core.tents import manager

    old_cwd = os.getcwd()
    old_path = manager.path
    try:
        with tempfile.TemporaryDirectory(prefix="growstar-phase4d-") as tmp:
            os.chdir(tmp)
            manager.path = str(Path(tmp) / "tents.json")
            manager.load()
            manager.save()

            manager.add_tent("phase4d_a", name="A")
            manager.add_tent("phase4d_b", name="B")
            ensure_tent_config("phase4d_a")
            ensure_tent_config("phase4d_b")

            snap_a = update_hardware_assignments(
                "phase4d_a",
                {"assignments": {"heating": {"ip": "192.0.2.10", "relay": 0}}},
            )
            checks["Hardware-Zuordnung wird stationslokal persistiert"] = (
                snap_a["assignments"]["heating"]["ip"] == "192.0.2.10"
                and snap_a["assignments"]["heating"]["relay"] == 0
            )

            try:
                update_hardware_assignments(
                    "phase4d_b",
                    {"assignments": {"light": {"ip": "192.0.2.10", "relay": 0}}},
                )
            except HardwareConflictError:
                conflict_blocked = True
            else:
                conflict_blocked = False
            checks["Gleiche IP+Relay-Kombination zwischen Stationen wird blockiert"] = conflict_blocked

            snap_b = update_hardware_assignments(
                "phase4d_b",
                {"assignments": {"light": {"ip": "192.0.2.10", "relay": 1}}},
            )
            checks["Gleiche IP mit anderem Relay bleibt erlaubt"] = snap_b["assignments"]["light"]["relay"] == 1

            before = manager.get("phase4d_b")
            try:
                manager.update_tent("phase4d_b", enabled=False, shadow_enabled=True)
            except ValueError:
                invalid_meta_blocked = True
            else:
                invalid_meta_blocked = False
            checks["Ungültiges Meta-Update bleibt atomar"] = invalid_meta_blocked and manager.get("phase4d_b") == before

            # Nicht verwendete Geräte dürfen trotz Relay-Vorauswahl leer bleiben.
            snap_a = update_hardware_assignments(
                "phase4d_a",
                {"assignments": {"heating": {"ip": "", "relay": 0}}},
            )
            checks["Leere IP entfernt eine vorhandene Zuordnung trotz Relay 0"] = (
                snap_a["assignments"]["heating"]["configured"] is False
                and snap_a["assignments"]["heating"]["ip"] == ""
                and snap_a["assignments"]["heating"]["relay"] is None
            )

            snap_a = update_hardware_assignments(
                "phase4d_a",
                {"assignments": {"heating": {"ip": "192.0.2.20", "relay": ""}}},
            )
            checks["IP ohne Relay verwendet automatisch Relay 0"] = (
                snap_a["assignments"]["heating"]["ip"] == "192.0.2.20"
                and snap_a["assignments"]["heating"]["relay"] == 0
            )

            checks["Default-LIVE-Station ist für Hardwarezuordnung editierbar"] = hardware_snapshot("tent_1")["editable"] is True
    finally:
        os.chdir(old_cwd)
        manager.path = old_path
        manager.load()

    failed = [name for name, ok in checks.items() if not ok]
    for name, ok in checks.items():
        print(("✅" if ok else "❌"), name)

    if failed:
        raise SystemExit("Phase 4D fehlgeschlagen: " + ", ".join(failed))

    print("✅ Phase 4D.1: optionale Aktoren + Shelly-Relay-0 + LIVE-Bearbeitung vollständig")


if __name__ == "__main__":
    main()
