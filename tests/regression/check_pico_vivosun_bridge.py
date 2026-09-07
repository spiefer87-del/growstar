#!/usr/bin/env python3
"""Regression checks for the Pico W VIVOSUN BLE-to-WiFi bridge."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import ast
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def load_bridge(relative):
    path = ROOT / relative
    spec = spec_from_file_location("pico_vivosun_bridge_test", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def encoded(value):
    raw = int(round(float(value) * 16))
    if raw < 0:
        raw += 0x10000
    return bytes((raw & 0xFF, (raw >> 8) & 0xFF))


def check_firmware_files():
    main_01 = read("pico_sensor_01/main.py")
    main_02 = read("pico_sensor_02/main.py")
    bridge_01 = read("pico_sensor_01/vivosun_ble.py")
    bridge_02 = read("pico_sensor_02/vivosun_ble.py")

    require(main_01 == main_02, "Beide Pico-Firmwares besitzen denselben Brückencode")
    require(bridge_01 == bridge_02, "Beide Pico-Firmwares besitzen denselben BLE-Adapter")

    for relative in (
        "pico_sensor_01/main.py",
        "pico_sensor_01/vivosun_ble.py",
        "pico_sensor_02/main.py",
        "pico_sensor_02/vivosun_ble.py",
    ):
        ast.parse(read(relative), filename=relative)
    require(True, "Pico-Brückendateien sind syntaktisch gültig")

    require(
        'getattr(local_config, "VIVOSUN_BRIDGE_TARGETS", ())' in main_01,
        "Bestehende Pico-config.py startet weiterhin ohne neue Brückenfelder",
    )
    main_loop = main_01[main_01.index("# Hauptprogramm"):]
    require(
        main_loop.index("publish_sensor_state()")
        < main_loop.index("publish_due_vivosun_bridge_state()"),
        "Lokale Pico-Sensoren werden vor dem langsameren BLE-Zyklus veröffentlicht",
    )
    require(
        'retain=False' in main_01
        and '"transport": "pico_wifi_ble_bridge"' in main_01,
        "VIVOSUN-State bleibt nicht retained und trägt seine Brückenherkunft",
    )

    for number in ("01", "02"):
        config = read("pico_sensor_%s/config.example.py" % number)
        require(
            "VIVOSUN_BRIDGE_TARGETS = (" in config
            and 'FIRMWARE_VERSION = "growstar-pico-mqtt-3"' in config,
            "Pico %s dokumentiert Firmware 3 und die optionale Zielzuordnung" % number,
        )


def check_protocol_decoder():
    bridge = load_bridge("pico_sensor_01/vivosun_ble.py")
    payload = bytearray(11)
    payload[1:3] = encoded(24.5)
    payload[3:5] = encoded(55.0)
    payload[7:9] = encoded(20.25)
    payload[9:11] = encoded(60.0)

    channels = bridge.decode_status_payload(payload)
    require(
        channels["main"] == {
            "temperature": 24.5,
            "humidity": 55.0,
            "available": True,
        },
        "Interner VS-THB1S-Kanal wird korrekt dekodiert",
    )
    require(
        channels["external"] == {
            "temperature": 20.25,
            "humidity": 60.0,
            "available": True,
        },
        "Externer VS-THB1S-Kanal wird korrekt dekodiert",
    )
    require(
        bridge.device_id_from_address("aa-bb-cc-dd-ee-ff", "main")
        == "vivosun_aabbccddeeff_main",
        "Virtuelle MQTT-Geräte-ID ist stabil aus MAC und Kanal abgeleitet",
    )

    missing_external = bytearray(payload)
    missing_external[7:9] = b"\xff\xff"
    missing_external[9:11] = b"\xff\xff"
    channels = bridge.decode_status_payload(missing_external)
    require(
        channels["main"]["available"]
        and not channels["external"]["available"],
        "Fehlender externer Fühler verwirft nicht den internen Kanal",
    )

    try:
        bridge.decode_status_payload(b"\x00\x01")
    except bridge.VivosunBridgeError:
        pass
    else:
        raise AssertionError("Zu kurze VIVOSUN-Pakete müssen abgewiesen werden")
    print("✅ Zu kurze VIVOSUN-Pakete werden abgewiesen")


def check_complete_gatt_transaction():
    bridge = load_bridge("pico_sensor_01/vivosun_ble.py")
    target_address = bytes((0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF))
    payload = bytearray(11)
    payload[1:3] = encoded(23.75)
    payload[3:5] = encoded(57.5)
    payload[7:9] = encoded(21.0)
    payload[9:11] = encoded(61.0)

    class FakeUUID:
        def __init__(self, value):
            self.value = value.value if isinstance(value, FakeUUID) else value

        def __eq__(self, other):
            return isinstance(other, FakeUUID) and self.value == other.value

    class FakeBLE:
        def __init__(self):
            self.handler = None
            self.calls = []

        def active(self, value):
            self.calls.append(("active", value))

        def config(self, **values):
            self.calls.append(("config", values))

        def irq(self, handler):
            self.handler = handler

        def gap_scan(self, duration, *args):
            self.calls.append(("scan", duration))
            if duration is None:
                self.handler(6, None)
                return
            name = bridge.LOCAL_NAME.encode()
            adv_data = bytes((len(name) + 1, 0x09)) + name
            self.handler(5, (0, target_address, 0, -61, adv_data))

        def gap_connect(self, addr_type, addr=None, *args):
            self.calls.append(("connect", addr_type))
            if addr_type is not None:
                self.handler(7, (1, addr_type, addr))

        def gap_disconnect(self, conn_handle):
            self.calls.append(("disconnect", conn_handle))
            self.handler(8, (conn_handle, 0, target_address))

        def gattc_discover_services(self, conn_handle, uuid):
            self.calls.append(("services", conn_handle))
            self.handler(9, (conn_handle, 10, 30, uuid))
            self.handler(10, (conn_handle, 0))

        def gattc_discover_characteristics(self, conn_handle, start, end):
            self.calls.append(("characteristics", start, end))
            self.handler(11, (
                conn_handle,
                12,
                13,
                0x10,
                FakeUUID(bridge._STATUS_UUID_TEXT),
            ))
            self.handler(11, (
                conn_handle,
                16,
                17,
                0x04,
                FakeUUID(bridge._COMMAND_UUID_TEXT),
            ))
            self.handler(12, (conn_handle, 0))

        def gattc_discover_descriptors(self, conn_handle, start, end):
            self.calls.append(("descriptors", start, end))
            self.handler(13, (conn_handle, 14, FakeUUID(0x2902)))
            self.handler(14, (conn_handle, 0))

        def gattc_write(self, conn_handle, value_handle, value, mode):
            self.calls.append(("write", value_handle, bytes(value), mode))
            if mode == 1:
                self.handler(17, (conn_handle, value_handle, 0))
            elif bytes(value) == b"\x0d":
                self.handler(18, (conn_handle, 13, bytes(payload)))

    class FakeBluetooth:
        UUID = FakeUUID

        def __init__(self):
            self.instance = FakeBLE()

        def BLE(self):
            return self.instance

    class FakeTime:
        now = 0

        @classmethod
        def ticks_ms(cls):
            return cls.now

        @staticmethod
        def ticks_add(value, delta):
            return value + delta

        @staticmethod
        def ticks_diff(left, right):
            return left - right

        @classmethod
        def sleep_ms(cls, value):
            cls.now += value

    fake_bluetooth = FakeBluetooth()
    bridge.bluetooth = fake_bluetooth
    bridge.time = FakeTime
    reader = bridge.VivosunTHB1SBridge()
    result = reader.read("AA:BB:CC:DD:EE:FF")
    calls = fake_bluetooth.instance.calls

    require(
        result["channels"]["main"]["temperature"] == 23.75
        and result["channels"]["external"]["humidity"] == 61.0,
        "Komplett simulierter GATT-Abruf liefert beide VIVOSUN-Kanäle",
    )
    require(
        ("write", 14, b"\x01\x00", 1) in calls
        and ("write", 17, b"\x0d", 0) in calls,
        "Pico aktiviert Notify-CCCD und sendet Statuskommando 0x0D",
    )
    require(
        ("disconnect", 1) in calls,
        "Pico trennt die BLE-Verbindung nach jedem Messwert sauber",
    )


def check_backend_bridge_lifecycle():
    from core.mqtt_sensor_devices import (
        clear_mqtt_sensor_devices,
        get_mqtt_sensor_device,
        update_mqtt_sensor_state,
        update_mqtt_sensor_status,
    )

    clear_mqtt_sensor_devices()
    child_id = "vivosun_aabbccddeeff_main"
    update_mqtt_sensor_state(
        child_id,
        {
            "name": "VIVOSUN Zelt 1 - Interner Sensor",
            "model": "VIVOSUN AeroLab VS-THB1S via Pico W",
            "device_class": "sensor",
            "transport": "pico_wifi_ble_bridge",
            "protocol": "vivosun_thb1s",
            "bridge_id": "pico_01",
            "bridge_name": "Pico Sensor 1",
            "ble_address": "AA:BB:CC:DD:EE:FF",
            "channel": "main",
            "temperature": 24.5,
            "humidity": 55.0,
        },
        now=100,
    )

    child = get_mqtt_sensor_device(child_id)
    require(
        child["online"]
        and child["bridge_id"] == "pico_01"
        and child["transport"] == "pico_wifi_ble_bridge",
        "Growstar-Inventar bewahrt Herkunft und Onlinezustand der Brückenquelle",
    )

    update_mqtt_sensor_status(
        "pico_01",
        {"online": False, "reason": "lost_connection"},
        now=200,
    )
    child = get_mqtt_sensor_device(child_id)
    require(
        not child["online"] and "lost_connection" in child["reason"],
        "Pico-Last-Will markiert abhängige VIVOSUN-Quellen offline",
    )

    update_mqtt_sensor_status(
        child_id,
        {
            "online": True,
            "bridge_id": "pico_01",
            "transport": "pico_wifi_ble_bridge",
        },
        now=300,
    )
    require(
        get_mqtt_sensor_device(child_id)["online"],
        "Ein echter Brückenstatus aktiviert die VIVOSUN-Quelle wieder",
    )
    clear_mqtt_sensor_devices()


def main():
    check_firmware_files()
    check_protocol_decoder()
    check_complete_gatt_transaction()
    check_backend_bridge_lifecycle()
    print("✅ Pico-VIVOSUN-Brückenregression vollständig erfolgreich")


if __name__ == "__main__":
    main()
