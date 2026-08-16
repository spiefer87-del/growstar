#!/usr/bin/env python3
"""Growstar Phase 4O – Gateway-IP-Hilfe + read-only Aktoransicht.

Hardware- und netzwerkfrei. Geprüft werden Syntax, UI-Grenzen und die reine
View-Verknüpfung von stationsbezogenen Zuordnungen mit Gateway-Snapshots.
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


def static_checks():
    route = read("routes/hardware.py")
    connections = read("templates/connections.html")
    devices = read("templates/devices.html")
    self_src = read("check_multi_tent_phase4o.py")

    ast.parse(route, filename="routes/hardware.py")
    ast.parse(self_src, filename="check_multi_tent_phase4o.py")
    print("✅ Python-Syntax Phase 4O")

    if Environment is not None:
        Environment().parse(connections)
        Environment().parse(devices)
        print("✅ Jinja/HTML-Syntax Phase 4O")

    require(
        'fetch("/api/hardware"' in connections
        and "gatewayOptions" in connections
        and "IP übernehmen" in connections,
        "Verbindungen bietet erkannte Gateways als reine IP-Eingabehilfe an",
    )
    require(
        'ipInput.value = String(gateway.ip || "").trim()' in connections,
        "Gateway-Übernahme kopiert explizit nur die IP",
    )
    copy_slice = connections[
        connections.index('grid.addEventListener("click"'):
        connections.index('select.addEventListener("change"')
    ]
    require(
        "relaySelect" not in copy_slice
        and 'method:"POST"' not in copy_slice,
        "IP-Übernahme verändert weder Relay noch speichert sie automatisch",
    )
    require(
        "modeLocked" in connections
        and "fieldsEditable" in connections
        and "hardware_assignment_active_mode" in connections
        and "hardware_assignment_not_safe_off" in connections,
        "Phase-4L-Zuordnungs- und Safety-Guards bleiben in der UI erhalten",
    )
    require(
        "assigned_actuators" in route
        and "_assigned_actuator_views" in route
        and "hardware_snapshot" in route,
        "Hardware-API liefert eine zusätzliche read-only Aktoransicht",
    )
    helper_slice = route[
        route.index("def _assigned_actuator_views"):
        route.index("def register(app)")
    ]
    require(
        "requests." not in helper_slice
        and "switch_shelly" not in helper_slice
        and "refresh" not in helper_slice,
        "Aktoransicht erzeugt keine Netzwerk-/Schaltbefehle",
    )
    require(
        "data.assigned_actuators" in devices
        and "Keine Aktor-Zuordnungen" in devices
        and "Gateway" in devices
        and "Firmware" in devices
        and "RSSI" in devices,
        "Hardware/Aktoren zeigt stationsbezogene Zuordnung und Gateway-Details",
    )
    require(
        "mqtt-device-grid" in devices
        and "MQTT Sensorcontroller" in devices
        and "data.mqtt_devices || []" in devices
        and "renderMqttDevices" in devices,
        "Bestehende Pico/MQTT-Sensorcontroller bleiben in der Hardware-Uebersicht erhalten",
    )
    require(
        "function formatUptime(seconds)" in devices,
        "Gemeinsamer Uptime-Formatter fuer MQTT-Sensoren und Aktor-Gatewaydetails bleibt vorhanden",
    )
    require(
        "Zugeordnet, aber die IP ist momentan keinem erkannten Gateway" in devices,
        "Manuelle unbekannte IP bleibt auf Hardwareseite sichtbar statt zu verschwinden",
    )


def dynamic_view_check():
    old_modules = dict(sys.modules)
    try:
        # Flask nur so weit faken, dass das Routenmodul importiert werden kann.
        flask = types.ModuleType("flask")
        flask.jsonify = lambda value=None, **kwargs: value if value is not None else kwargs
        flask.request = object()
        sys.modules["flask"] = flask

        services = types.ModuleType("services")
        services.__path__ = []
        sys.modules["services"] = services
        hw_mod = types.ModuleType("services.hardware")
        hw_mod.hardware = object()
        sys.modules["services.hardware"] = hw_mod

        core = types.ModuleType("core")
        core.__path__ = []
        sys.modules["core"] = core

        mqtt = types.ModuleType("core.mqtt_sensor_devices")
        mqtt.list_mqtt_sensor_devices = lambda: []
        sys.modules["core.mqtt_sensor_devices"] = mqtt

        assignments = types.ModuleType("core.hardware_assignments")
        assignments.hardware_snapshot = lambda tent_id: {}
        sys.modules["core.hardware_assignments"] = assignments

        tents_mod = types.ModuleType("core.tents")
        tents_mod.manager = type("M", (), {"list_tents": lambda self: []})()
        sys.modules["core.tents"] = tents_mod

        spec = importlib.util.spec_from_file_location(
            "phase4o_hardware_route",
            ROOT / "routes" / "hardware.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        gateways = [
            {
                "id": "gw_a",
                "name": "Shelly Plug Mini Gen3",
                "model": "S3PL-00112EU",
                "manufacturer": "Shelly",
                "ip": "192.0.2.10",
                "online": True,
                "firmware": "1.0.0",
                "rssi": -51,
                "uptime": 1234,
                "mac": "AA:BB:CC:DD:EE:FF",
            }
        ]

        snapshots = {
            "tent_1": {
                "name": "Zelt 1",
                "assignments": {
                    "heating": {
                        "device": "heating",
                        "label": "Heizung",
                        "icon": "🔥",
                        "mode": "ENV",
                        "ip": "192.0.2.10",
                        "relay": 0,
                        "configured": True,
                    },
                    "vent": {
                        "device": "vent",
                        "label": "Ventilator",
                        "icon": "🌀",
                        "mode": "OFF",
                        "ip": "manual.local",
                        "relay": 1,
                        "configured": True,
                    },
                    "light": {
                        "device": "light",
                        "configured": False,
                    },
                },
            },
            "tent_2": {
                "name": "Zelt 2",
                "assignments": {
                    "dehumidifier": {
                        "device": "dehumidifier",
                        "label": "Entfeuchter",
                        "icon": "🌬️",
                        "mode": "ON",
                        "ip": "192.0.2.10",
                        "relay": 1,
                        "configured": True,
                    },
                },
            },
        }

        rows = module._assigned_actuator_views(
            gateways,
            tents=[
                {"id": "tent_1", "name": "Zelt 1"},
                {"id": "tent_2", "name": "Zelt 2"},
            ],
            snapshot_loader=lambda tent_id: snapshots[tent_id],
        )

        require(len(rows) == 3, "Nur tatsächlich zugewiesene Aktoren werden gelistet")

        heating = next(row for row in rows if row["device"] == "heating")
        require(
            heating["gateway_detected"] is True
            and heating["gateway"]["firmware"] == "1.0.0"
            and heating["gateway"]["rssi"] == -51,
            "Passende Gateway-IP ergänzt Modell-/Firmware-/RSSI-Daten",
        )

        manual = next(row for row in rows if row["device"] == "vent")
        require(
            manual["gateway_detected"] is False
            and manual["gateway"] is None
            and manual["ip"] == "manual.local",
            "Manuell zugewiesener unbekannter Host bleibt unverändert erhalten",
        )

        same_gateway = [row for row in rows if row["ip"] == "192.0.2.10"]
        require(
            len(same_gateway) == 2
            and {row["relay"] for row in same_gateway} == {0, 1},
            "Eine Gateway-IP kann weiterhin mehreren unterschiedlichen Relays zugeordnet sein",
        )

    finally:
        sys.modules.clear()
        sys.modules.update(old_modules)


def main():
    static_checks()
    dynamic_view_check()
    print("✅ Phase 4O Gateway-IP-Hilfe / Hardware-Aktoransicht vollständig")


if __name__ == "__main__":
    main()
