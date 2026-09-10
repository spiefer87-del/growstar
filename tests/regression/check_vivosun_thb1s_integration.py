#!/usr/bin/env python3
"""Regressionstest fuer den lokalen VIVOSUN-AeroLab-BLE-Pfad."""

from copy import deepcopy
from pathlib import Path
import struct
import sys
import tempfile
import types
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def status_payload(
    main_temperature=24.5,
    main_humidity=58.0,
    external_temperature=23.25,
    external_humidity=61.5,
):
    payload = bytearray(11)
    payload[0] = 0x0D
    for offset, value in (
        (1, main_temperature),
        (3, main_humidity),
        (7, external_temperature),
        (9, external_humidity),
    ):
        raw = -1 if value is None else round(float(value) * 16)
        struct.pack_into("<h", payload, offset, raw)
    return bytes(payload)


def advertisement_payload(
    main_temperature=19.0625,
    main_humidity=53.0,
    external_temperature=18.8125,
    external_humidity=53.8125,
    battery_voltage=3.872,
    uptime_seconds=2520,
):
    payload = bytearray(20)
    payload[3:6] = bytes((0xC7, 0x65, 0xEE))
    struct.pack_into("<H", payload, 6, round(float(battery_voltage) * 1000))
    for offset, value in (
        (8, main_temperature),
        (10, main_humidity),
        (12, external_temperature),
        (14, external_humidity),
    ):
        raw = -1 if value is None else round(float(value) * 16)
        struct.pack_into("<h", payload, offset, raw)
    struct.pack_into("<I", payload, 16, int(uptime_seconds))
    return bytes(payload)


class FakeBleDevice:
    address = "AA:BB:CC:DD:EE:FF"
    name = "ThermoBeacon2"
    rssi = -47


class FakeScanner:
    anonymous = SimpleNamespace(
        address="EE:65:C7:00:00:00",
        name=None,
        rssi=None,
    )

    @staticmethod
    async def discover(timeout, *, return_adv=False):
        assert 2 <= timeout <= 30
        named = FakeBleDevice()
        other = SimpleNamespace(
            address="11:22:33:44:55:66",
            name="Other",
            rssi=-80,
        )
        devices = [named, FakeScanner.anonymous, other]
        if not return_adv:
            return devices

        return {
            named.address: (
                named,
                SimpleNamespace(
                    local_name="ThermoBeacon2",
                    manufacturer_data={},
                    service_uuids=[],
                    rssi=-47,
                ),
            ),
            FakeScanner.anonymous.address: (
                FakeScanner.anonymous,
                SimpleNamespace(
                    local_name=None,
                    manufacturer_data={0x0019: advertisement_payload()},
                    service_uuids=[
                        "0000fff0-0000-1000-8000-00805f9b34fb",
                    ],
                    rssi=-34,
                ),
            ),
            other.address: (
                other,
                SimpleNamespace(
                    local_name="Other",
                    manufacturer_data={},
                    service_uuids=[],
                    rssi=-80,
                ),
            ),
        }

    @staticmethod
    async def find_device_by_address(address, timeout):
        assert address == FakeBleDevice.address
        assert timeout > 0
        return FakeBleDevice()


class FakeClient:
    connect_calls = 0
    last_command = None
    last_command_uuid = None
    last_status_uuid = None

    def __init__(self, device, timeout):
        assert device.address == FakeBleDevice.address
        assert timeout > 0
        self.callback = None

    async def connect(self):
        FakeClient.connect_calls += 1
        return True

    async def start_notify(self, uuid, callback):
        self.callback = callback
        FakeClient.last_status_uuid = uuid

    async def write_gatt_char(self, uuid, command):
        FakeClient.last_command_uuid = uuid
        FakeClient.last_command = bytes(command)
        self.callback(1, status_payload())

    async def stop_notify(self, uuid):
        assert uuid == FakeClient.last_status_uuid

    async def disconnect(self):
        return True


class TimeoutClient(FakeClient):
    async def connect(self):
        raise TimeoutError


def check_decoder_and_adapter():
    from core.hardware.vivosun import (
        COMMAND_UUID,
        READ_STATUS_COMMAND,
        STATUS_UUID,
        VivosunBleError,
        VivosunTHB1SAdapter,
        decode_advertisement_payload,
        decode_status_payload,
        device_id_from_address,
    )

    decoded = decode_status_payload(status_payload())
    require(
        decoded["channels"]["main"]["temperature"] == 24.5
        and decoded["channels"]["main"]["humidity"] == 58.0
        and decoded["channels"]["external"]["temperature"] == 23.25
        and decoded["channels"]["external"]["humidity"] == 61.5,
        "VS-THB1S-Statuspaket dekodiert beide Temperatur-/Feuchtekanäle",
    )

    missing = decode_status_payload(
        status_payload(external_temperature=None, external_humidity=None)
    )
    require(
        missing["channels"]["main"]["available"] is True
        and missing["channels"]["external"]["available"] is False,
        "Nicht angeschlossener externer Fühler wird ohne Verlust des Hauptsensors erkannt",
    )

    try:
        decode_status_payload(b"\x0d\x00")
    except VivosunBleError:
        pass
    else:
        raise AssertionError("Zu kurzes VIVOSUN-Paket wurde akzeptiert")
    print("✅ Zu kurze oder unvollständige Statuspakete werden verworfen")

    advertisement = decode_advertisement_payload(advertisement_payload())
    require(
        advertisement["channels"]["main"]["temperature"] == 19.06
        and advertisement["channels"]["main"]["humidity"] == 53.0
        and advertisement["channels"]["external"]["temperature"] == 18.81
        and advertisement["channels"]["external"]["humidity"] == 53.81
        and advertisement["battery_voltage"] == 3.872
        and advertisement["uptime_seconds"] == 2520
        and advertisement["measurement_source"] == "advertisement",
        "VS-THB1S-Advertisement dekodiert Messwerte, Batterie und Laufzeit",
    )

    adapter = VivosunTHB1SAdapter(
        scanner_cls=FakeScanner,
        client_cls=FakeClient,
        now=lambda: 1_700_000_000.0,
    )
    scan = adapter.scan(timeout=2)
    addresses = {item["address"] for item in scan["candidates"]}
    require(
        scan["success"] is True
        and scan["count"] == 2
        and FakeBleDevice.address in addresses
        and FakeScanner.anonymous.address in addresses,
        "Discovery akzeptiert ThermoBeacon2 und den namenlosen VS-THB1S-Advert",
    )
    for manufacturer_id in (0x0019, 0x8019):
        advertisement = SimpleNamespace(
            local_name=None,
            manufacturer_data={manufacturer_id: advertisement_payload()},
            service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
        )
        require(
            adapter._is_supported(FakeScanner.anonymous, advertisement),
            f"ManufacturerData 0x{manufacturer_id:04X} wird als VS-THB1S erkannt",
        )

    invalid_advertisement = SimpleNamespace(
        local_name=None,
        manufacturer_data={0x0019: bytes(19)},
        service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
    )
    require(
        not adapter._is_supported(FakeScanner.anonymous, invalid_advertisement),
        "Unvollständige oder fremde ManufacturerData wird nicht akzeptiert",
    )

    reading = adapter.read(FakeBleDevice.address)
    require(
        reading["success"] is True
        and reading["observed_at"] == 1_700_000_000.0
        and FakeClient.last_command == READ_STATUS_COMMAND
        and FakeClient.last_command_uuid == COMMAND_UUID
        and FakeClient.last_status_uuid == STATUS_UUID,
        "Direkter GATT-Read verwendet Status-Notification und Read-Kommando 0x0D",
    )
    gatt_connect_calls = FakeClient.connect_calls
    passive_reading = adapter.read(FakeScanner.anonymous.address)
    require(
        passive_reading["success"] is True
        and passive_reading["measurement_source"] == "advertisement"
        and passive_reading["advertisement_manufacturer_id"] == 0x0019
        and passive_reading["channels"]["main"]["temperature"] == 19.06
        and FakeClient.connect_calls == gatt_connect_calls,
        "Namenloser VS-THB1S wird ohne aktive GATT-Verbindung ausgelesen",
    )
    require(
        device_id_from_address("aa:bb:cc:dd:ee:ff") == "vivosun_aabbccddeeff",
        "Persistente Geräte-ID wird stabil aus der BLE-Adresse gebildet",
    )

    timeout_adapter = VivosunTHB1SAdapter(
        scanner_cls=FakeScanner,
        client_cls=TimeoutClient,
    )
    timeout_result = timeout_adapter.read(FakeBleDevice.address)
    require(
        timeout_result["success"] is False
        and timeout_result["error"].endswith("TimeoutError"),
        "Leere BLE-Ausnahmen werden mit ihrem Fehlerklassennamen ausgegeben",
    )


class FakeServiceAdapter:
    def status(self):
        return {"success": True, "available": True}

    def scan(self, timeout=8):
        return {
            "success": True,
            "available": True,
            "count": 1,
            "candidates": [{
                "address": FakeBleDevice.address,
                "name": FakeBleDevice.name,
                "rssi": FakeBleDevice.rssi,
                "model": "VS-THB1S",
            }],
        }

    def read(self, address):
        return {
            "success": True,
            "address": address,
            "name": FakeBleDevice.name,
            "rssi": FakeBleDevice.rssi,
            "observed_at": 1_700_000_000.0,
            "raw_hex": status_payload().hex(),
            "measurement_source": "advertisement",
            "battery_voltage": 3.872,
            "uptime_seconds": 2520,
            "advertisement_manufacturer_id": 0x0019,
            "channels": decode_for_service(),
        }


def decode_for_service():
    from core.hardware.vivosun import decode_status_payload

    return decode_status_payload(status_payload())["channels"]


def check_service_sources_and_recovery():
    import core.state as controller_state
    from core.hardware.manager import HardwareManager
    from core.hardware.recovery import HardwareRecoveryCoordinator
    from core.sensor_sources import list_sensor_sources

    # Der schlanke CI-Container besitzt absichtlich keine Shelly-/mDNS-
    # Abhängigkeiten. Dieser Test ruft die Discovery nicht auf und ersetzt nur
    # den optionalen Discovery-Import, bevor der Service geladen wird.
    if "core.hardware.shelly.discovery" not in sys.modules:
        discovery_stub = types.ModuleType("core.hardware.shelly.discovery")
        discovery_stub.ShellyDiscovery = type("ShellyDiscovery", (), {})
        sys.modules["core.hardware.shelly.discovery"] = discovery_stub

    import services.hardware as hardware_module

    original_manager = hardware_module.manager
    original_adapter = hardware_module.vivosun_adapter
    original_sources = deepcopy(controller_state.live_state.get("sensor_sources", {}))

    try:
        with tempfile.TemporaryDirectory(prefix="growstar-vivosun-") as tmp:
            manager = HardwareManager(
                Path(tmp) / "hardware_inventory.json",
                autoload=False,
            )
            hardware_module.manager = manager
            hardware_module.vivosun_adapter = FakeServiceAdapter()
            controller_state.live_state["sensor_sources"] = {}

            service = object.__new__(hardware_module.HardwareService)
            result = service.register_vivosun_device(FakeBleDevice.address)
            require(
                result["success"] is True
                and result["device"]["properties"]["protocol"] == "vivosun_thb1s"
                and result["device"]["properties"]["preferred_channel"] == "external"
                and result["device"]["properties"]["measurement_source"]
                == "advertisement"
                and result["device"]["properties"]["battery_voltage"] == 3.872
                and result["device"]["properties"]["sensor_uptime"] == 2520,
                "Registrierung übernimmt den geprüften VS-THB1S persistent in Growstar",
            )

            source_ids = {source["id"] for source in list_sensor_sources()}
            require(
                source_ids == {
                    "hardware:vivosun_aabbccddeeff:main",
                    "hardware:vivosun_aabbccddeeff:external",
                },
                "Interner Sensor und externer Fühler erscheinen als getrennte Sensorquellen",
            )
            require(
                (Path(tmp) / "hardware_inventory.json").exists(),
                "VIVOSUN-Registrierung wird im Hardware-Inventar gespeichert",
            )

            device = manager.device("vivosun_aabbccddeeff")
            device.online = False

            class RecoveryHardware:
                @staticmethod
                def scan_gateways():
                    return 0

                @staticmethod
                def read_ble_sensor_values(device_id, listen=False):
                    assert listen is False
                    manager.device(device_id).online = True
                    return {"success": True}

            recovery = HardwareRecoveryCoordinator(
                hardware=RecoveryHardware(),
                manager=manager,
                expected_device_ids_provider=lambda: [],
                sleep=lambda _seconds: None,
                now=lambda: 1_700_000_001.0,
                ble_scan_settle_sec=0,
            )
            snapshot = recovery.recover_once()
            require(
                snapshot["healthy"] is True
                and snapshot["expected_ble_devices"] == 1
                and snapshot["online_ble_devices"] == 1
                and snapshot["gateway_scan_used"] is True
                and snapshot["ble_scan_used"] is False,
                "VS-THB1S-Recovery funktioniert ohne Shelly-Gateway und BTHome-Scan",
            )
    finally:
        hardware_module.manager = original_manager
        hardware_module.vivosun_adapter = original_adapter
        controller_state.live_state["sensor_sources"] = original_sources


def check_routes_ui_permissions():
    from auth.policy import permission_requirement

    routes = (ROOT / "routes" / "hardware.py").read_text(encoding="utf-8")
    devices = (ROOT / "templates" / "devices.html").read_text(encoding="utf-8")
    detail = (ROOT / "templates" / "blu_device.html").read_text(encoding="utf-8")
    detail_js = (ROOT / "static" / "js" / "blu_device.js").read_text(encoding="utf-8")
    thread = (ROOT / "threads" / "blu.py").read_text(encoding="utf-8")

    require(
        '@app.post("/api/hardware/vivosun/scan")' in routes
        and '@app.post("/api/hardware/vivosun/register")' in routes
        and "/api/hardware/vivosun/status" in routes,
        "Hardware-API bietet Status, Scan und geprüfte VIVOSUN-Registrierung",
    )
    require(
        "VS-THB1S suchen" in devices
        and "ThermoBeacon2" in devices
        and "Verbinden & Messwerte prüfen" in devices,
        "Hardware-Seite führt verständlich durch Pairing, Suche und Verbindung",
    )
    render_gateways = devices.index("function renderGateways")
    render_devices = devices.index("function renderDevices")
    format_uptime = devices.index("function formatUptime")
    require(
        "const isVivosun" not in devices[render_gateways:render_devices]
        and "const isVivosun" in devices[render_devices:format_uptime],
        "VIVOSUN-Kartendarstellung ist ausschließlich im Bluetooth-Geräterenderer aktiv",
    )
    require(
        "vivosun-main-temperature" in detail
        and "vivosun-external-humidity" in detail
        and 'props.protocol === "vivosun_thb1s"' in detail_js,
        "Gerätedetail zeigt beide VIVOSUN-Messkanäle getrennt an",
    )
    require(
        "VIVOSUN_PROTOCOL" in thread and "read_ble_sensor_values" in thread,
        "Bestehender BLU-Thread aktualisiert den VS-THB1S automatisch",
    )

    scan_permission = permission_requirement("/api/hardware/vivosun/scan", "POST")
    register_permission = permission_requirement("/api/hardware/vivosun/register", "POST")
    require(
        scan_permission.permissions == ("hardware.control",)
        and register_permission.permissions == ("hardware.configure",),
        "Scan und dauerhafte Registrierung besitzen getrennte Hardware-Rechte",
    )


def main():
    check_decoder_and_adapter()
    check_service_sources_and_recovery()
    check_routes_ui_permissions()
    print("✅ VIVOSUN VS-THB1S Integration vollständig erfolgreich")


if __name__ == "__main__":
    main()
