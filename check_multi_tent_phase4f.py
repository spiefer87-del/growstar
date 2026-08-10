#!/usr/bin/env python3
"""Phase 4F: Hardware Auto-Recovery ohne echte Netzwerk-/Pairingaufrufe testen."""

import ast
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def load_recovery_module():
    path = ROOT / "core/hardware/recovery.py"
    spec = importlib.util.spec_from_file_location("phase4f_recovery", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeGateway:
    def __init__(self, gateway_id="gw-1", *, bluetooth=True):
        self.id = gateway_id
        self.online = False
        self.bluetooth = bluetooth
        self.bluetooth_enabled = False
        self.methods = ["Bluetooth.SetConfig"] if bluetooth else []
        self.capabilities = {}


class FakeDevice:
    def __init__(self, device_id, *, online=False, paired=True):
        self.id = device_id
        self.type = "sensor"
        self.online = online
        self.properties = {
            "protocol": "bthome",
            "paired": paired,
        }


class FakeManager:
    def __init__(self, gateways=None, devices=None):
        self.gateways = {g.id: g for g in (gateways or [])}
        self.devices = {d.id: d for d in (devices or [])}
        self.saved = 0
        self.last_inventory_error = None

    def gateways_list(self):
        return list(self.gateways.values())

    def devices_list(self):
        return list(self.devices.values())

    def device(self, device_id):
        return self.devices.get(device_id)

    def save_inventory(self, merge=True):
        self.saved += 1
        return {"merge": merge}


class FakeHardware:
    def __init__(self, manager, expected_id):
        self.manager = manager
        self.expected_id = expected_id
        self.gateway_scans = 0
        self.ble_scans = 0
        self.pair_calls = 0
        self.read_calls = 0

    def refresh_gateway(self, gateway_id):
        gateway = self.manager.gateways.get(gateway_id)
        if gateway:
            gateway.online = True
        return gateway

    def scan_gateways(self):
        self.gateway_scans += 1
        if not self.manager.gateways:
            gateway = FakeGateway("gw-auto", bluetooth=True)
            gateway.online = True
            self.manager.gateways[gateway.id] = gateway
        return list(self.manager.gateways.values())

    def read_ble_sensor_values(self, device_id, listen=False):
        self.read_calls += 1
        device = self.manager.devices.get(device_id)
        if device:
            device.online = True
            return {"success": True}
        return None

    def enable_bluetooth(self, gateway_id):
        gateway = self.manager.gateways[gateway_id]
        gateway.bluetooth_enabled = True
        return True

    def start_ble_scan(self, gateway_id):
        self.ble_scans += 1
        return {"started": True}

    def get_ble_scan_result(self, gateway_id):
        return {"devices": [{"id": self.expected_id}]}

    def add_discovered_ble_devices(self, gateway_id):
        return {"success": True}

    def register_discovered_ble_devices(self, gateway_id):
        if self.expected_id not in self.manager.devices:
            self.manager.devices[self.expected_id] = FakeDevice(
                self.expected_id,
                online=False,
                paired=True,
            )
        return {"success": True}

    # Absichtlich vorhanden, damit der Test beweisen kann, dass Recovery es
    # niemals aufruft.
    def pair_ble_device(self, *args, **kwargs):
        self.pair_calls += 1
        raise AssertionError("Auto-Recovery darf nicht automatisch pairen")


def main():
    python_files = [
        "app.py",
        "core/hardware/manager.py",
        "core/hardware/recovery.py",
        "services/hardware_recovery.py",
        "threads/hardware.py",
        "core/watchdog_health.py",
    ]
    for rel in python_files:
        ast.parse(read(rel), filename=rel)
    print("✅ Python-Syntax Phase 4F")

    manager_src = read("core/hardware/manager.py")
    recovery_src = read("core/hardware/recovery.py")
    service_src = read("services/hardware_recovery.py")
    app_src = read("app.py")
    thread_src = read("threads/hardware.py")
    watchdog_src = read("core/watchdog_health.py")
    template = read("templates/watchdog.html")

    require("instance" in manager_src and "hardware_inventory.json" in manager_src,
            "Hardware-Inventar wird persistent in instance gespeichert")
    require("os.replace" in manager_src and "mkstemp" in manager_src,
            "Hardware-Inventar wird atomar geschrieben")
    require("gateway.online = False" in manager_src and "device.online = False" in manager_src,
            "Persistierte Hardware wird nach Neustart nicht fälschlich als online markiert")
    require("merge=True" in manager_src,
            "Scanner-Clears löschen bekannte Recovery-Daten nicht versehentlich")
    require("source_id.startswith(\"hardware:blu_\")" in service_src,
            "Erwartete BLE-Sensoren werden aus allen Stationszuweisungen abgeleitet")
    require("start_hardware_recovery_thread()" in app_src,
            "Backend startet Hardware Auto-Recovery automatisch")
    require("manager.save_inventory(merge=True)" in thread_src,
            "Normaler Hardware-Poll hält Recovery-Inventar aktuell")
    require("growstar-hw-recovery" in watchdog_src and "hardware_recovery" in watchdog_src,
            "Watchdog kennt den Recovery-Thread und Recovery-Status")
    require("Hardware Auto-Recovery" in template,
            "Watchdog-Oberfläche zeigt Hardware Auto-Recovery")
    require("pair_ble_device" not in recovery_src,
            "Recovery enthält keinen automatischen Pairing-Aufruf")

    module = load_recovery_module()
    Coordinator = module.HardwareRecoveryCoordinator

    expected = "blu_fc4d6a38def2"

    # Fall 1: Persistierter Gateway + persistiertes BLE-Gerät. Direkter Read
    # reicht; ein BLE-Scan ist nicht nötig.
    manager = FakeManager(
        gateways=[FakeGateway("gw-known", bluetooth=True)],
        devices=[FakeDevice(expected, online=False, paired=True)],
    )
    hardware = FakeHardware(manager, expected)
    coordinator = Coordinator(
        hardware=hardware,
        manager=manager,
        expected_device_ids_provider=lambda: [expected],
        sleep=lambda _: None,
        now=lambda: 1000.0,
        ble_scan_settle_sec=0,
    )
    result = coordinator.recover_once()

    require(result["healthy"] is True,
            "Persistierte bekannte Hardware wird ohne manuellen Scan wieder online")
    require(hardware.gateway_scans == 0,
            "Bekannter erreichbarer Gateway löst keinen unnötigen Netzwerkscan aus")
    require(hardware.ble_scans == 0,
            "Direkt lesbarer bekannter BLE-Sensor löst keinen unnötigen BLE-Scan aus")
    require(manager.saved >= 1,
            "Erfolgreiche Recovery persistiert den aktualisierten Bestand")

    # Fall 2: Erststart nach Installation: Inventar fehlt, Station erwartet aber
    # bereits einen hardware:blu_... Sensor. Gateway- und BLE-Discovery laufen
    # im Recovery-Thread und der erwartete Sensor wird wieder registriert.
    manager2 = FakeManager()
    hardware2 = FakeHardware(manager2, expected)
    coordinator2 = Coordinator(
        hardware=hardware2,
        manager=manager2,
        expected_device_ids_provider=lambda: [expected],
        sleep=lambda _: None,
        now=lambda: 2000.0,
        ble_scan_settle_sec=0,
    )
    result2 = coordinator2.recover_once()

    require(hardware2.gateway_scans == 1,
            "Fehlender Gateway wird beim Bootstrap automatisch gesucht")
    require(hardware2.ble_scans == 1,
            "Fehlender erwarteter BLE-Sensor startet automatisch BLE-Recovery")
    require(result2["healthy"] is True and result2["online_ble_devices"] == 1,
            "Erwarteter BLE-Sensor wird nach Discovery automatisch wieder verfügbar")
    require(hardware2.pair_calls == 0,
            "Unbekannte Geräte werden niemals automatisch gepairt")

    print("✅ Phase 4F Hardware Auto-Recovery vollständig")


if __name__ == "__main__":
    main()
