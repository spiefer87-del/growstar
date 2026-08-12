#!/usr/bin/env python3
"""Phase 4J.1 – BLE Direct-Read / Recovery Regression.

Keine produktiven Imports, keine Shelly-Requests, keine BLE-Scans.
Die echte Methode `read_ble_sensor_values()` wird per AST aus dem Patch
extrahiert und ausschließlich gegen Fakes ausgeführt.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SERVICE = ROOT / "services" / "hardware.py"


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def _source_and_method():
    source = SERVICE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SERVICE))

    raw_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "_apply_raw_sensor_values":
                raw_calls.append(node.lineno)

    require(not raw_calls,
            "Toter _apply_raw_sensor_values-Aufruf ist entfernt")

    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "HardwareService":
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == "read_ble_sensor_values":
                    segment = ast.get_source_segment(source, child)
                    if segment:
                        return source, textwrap.dedent(segment)

    raise AssertionError("HardwareService.read_ble_sensor_values nicht gefunden")


class FakeDevice:
    def __init__(self):
        self.id = "blu_test"
        self.name = "Test BLU"
        self.model = "Shelly BLU H&T"
        self.type = "sensor"
        self.online = False
        self.properties = {
            "gateway_id": "gw-1",
            "bthome_device_key": "bthomedevice:7",
            "last_seen": 123.0,
        }

    def to_dict(self):
        return {
            "id": self.id,
            "online": self.online,
            "properties": dict(self.properties),
        }


class FakeGateway:
    def __init__(self, *, status=None, config=None, known_objects=None):
        self.status = status
        self.config = config
        self.known_objects = known_objects
        self.listen_calls = 0

    def listen_for_sensor_updates(self, duration):
        self.listen_calls += 1
        raise AssertionError("listen=False darf keinen Listener starten")

    def get_bthome_device_status(self, key):
        return self.status

    def get_bthome_device_config(self, key):
        return self.config

    def get_bthome_device_known_objects(self, key):
        return self.known_objects


class FakeManager:
    def __init__(self, gateway):
        self._gateway = gateway

    def gateway(self, gateway_id):
        return self._gateway if gateway_id == "gw-1" else None


def _build_service(gateway, *, cache_applied=False, sensor_values_applied=False):
    source, method = _source_and_method()

    require("direct_read_confirmed" in source,
            "Direkter BTHome-Read besitzt explizite Recovery-Bestätigung")
    require('"Raw Sensor Werte Fehler:"' not in source,
            "Wiederkehrende Raw-Sensor-Fehlerzeile ist entfernt")

    namespace = {}
    exec(
        "import time\n\nclass ExtractedHardwareService:\n"
        + textwrap.indent(method, "    "),
        namespace,
    )

    cls = namespace["ExtractedHardwareService"]
    service = cls()
    device = FakeDevice()

    service.device = lambda device_id: device if device_id == "blu_test" else None
    service._apply_known_bthome_values_to_device = (
        lambda gw, dev: bool(cache_applied)
    )
    service._apply_known_objects_values = (
        lambda gw, dev, known: bool(sensor_values_applied)
    )
    service._publish_device_sensor_source = (
        lambda dev: {"id": "hardware:blu_test"}
    )

    manager = FakeManager(gateway)
    service.read_ble_sensor_values.__func__.__globals__["manager"] = manager

    return service, device


def main():
    ast.parse(SERVICE.read_text(encoding="utf-8"), filename=str(SERVICE))
    print("✅ Python-Syntax services/hardware.py")

    # Persistiertes Gerät ist zunächst offline, das Gateway kennt es aber.
    gateway = FakeGateway(
        status={"battery": 81},
        config={"name": "Test BLU"},
        known_objects=None,
    )
    service, device = _build_service(gateway)
    result = service.read_ble_sensor_values("blu_test", listen=False)

    require(result["success"] is True,
            "Direkter BLE-Read bleibt erfolgreich")
    require(result["direct_read_confirmed"] is True,
            "Status/Config bestätigen bekannten BTHome-Sensor")
    require(device.online is True,
            "Bekannter BLE-Sensor wird nach Direct-Read online markiert")
    require(device.properties.get("online") is True,
            "Properties spiegeln bestätigten Onlinezustand")
    require(device.properties.get("last_seen") == 123.0,
            "Recovery erfindet keinen Sensor-last_seen-Zeitstempel")
    require(gateway.listen_calls == 0,
            "listen=False startet keinen WebSocket-Listener")

    # Keine Evidenz: Sensor darf nicht blind online werden.
    empty_gateway = FakeGateway(
        status=None,
        config=None,
        known_objects=None,
    )
    service2, device2 = _build_service(empty_gateway)
    result2 = service2.read_ble_sensor_values("blu_test", listen=False)

    require(result2["direct_read_confirmed"] is False,
            "Ohne BTHome-Evidenz wird Direct-Read nicht bestätigt")
    require(device2.online is False,
            "Unbestätigter Sensor bleibt offline")
    require(device2.properties.get("last_seen") == 123.0,
            "Unbestätigter Read verändert Sensor-Freshness nicht")

    print("✅ Phase 4J.1 BLE Direct-Read / Recovery vollständig")


if __name__ == "__main__":
    main()
