#!/usr/bin/env python3
"""Regression für VIVOSUN-Transportübergabe und Shelly-Inventarbereinigung."""

from pathlib import Path
import json
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    import core.state as controller_state
    from core.hardware.device import HardwareDevice
    from core.hardware.gateway import Gateway
    from core.hardware.manager import HardwareManager
    from core.hardware.recovery import HardwareRecoveryCoordinator
    from core.hardware.vivosun import source_id_from_address
    from core.sensor_sources import update_sensor_source
    from core.hardware.visibility import hardware_device_views, mqtt_device_views

    address = "EE:65:C7:00:00:00"
    device = HardwareDevice(
        id="vivosun_ee65c7000000",
        name="VIVOSUN AeroLab",
        model="VS-THB1S",
        type="sensor",
        online=False,
        properties={
            "protocol": "vivosun_thb1s",
            "addr": address,
            "paired": True,
            "registered": True,
        },
    )
    previous_sources = controller_state.live_state.get("sensor_sources", {})
    try:
        controller_state.live_state["sensor_sources"] = {}
        update_sensor_source(
            source_id_from_address(address, "main"),
            source_type="mqtt",
            temperature=19.4,
            humidity=55.8,
            observed_at=1_700_000_000.0,
        )

        with tempfile.TemporaryDirectory(prefix="growstar-vivosun-transport-") as temp_dir:
            manager = HardwareManager(
                Path(temp_dir) / "hardware_inventory.json",
                autoload=False,
            )
            manager.add_device(device)

            class RecoveryHardware:
                @staticmethod
                def scan_gateways():
                    return 0

            recovery = HardwareRecoveryCoordinator(
                hardware=RecoveryHardware(),
                manager=manager,
                expected_device_ids_provider=lambda: [device.id],
                sleep=lambda _seconds: None,
                now=lambda: 1_700_000_001.0,
                ble_scan_settle_sec=0,
            )
            snapshot = recovery.recover_once()
            require(
                snapshot["healthy"] is True
                and snapshot["expected_ble_devices"] == 0
                and snapshot["missing_ble_devices"] == [],
                "Frischer Pico/MQTT-Transport ersetzt den lokalen VIVOSUN im Recovery-Count",
            )
        require(
            hardware_device_views([device], mqtt_vivosun_addresses={"ee65c7000000"}) == [],
            "Inaktiver Raspberry-Zwilling wird auf der Hardwareseite ausgeblendet",
        )
        visible_mqtt = mqtt_device_views([
            {"id": "pico_02", "name": "Pico Sensor 2"},
            {"id": "vivosun_ee65c7000000_main", "protocol": "vivosun_thb1s"},
            {"id": "vivosun_ee65c7000000_external", "protocol": "vivosun_thb1s"},
        ])
        require(
            [item["id"] for item in visible_mqtt] == ["pico_02"],
            "VIVOSUN-Kanäle bleiben Sensorquellen, erscheinen aber nicht als drei Hardwaregeräte",
        )
    finally:
        controller_state.live_state["sensor_sources"] = previous_sources

    with tempfile.TemporaryDirectory(prefix="growstar-gateway-dedupe-") as temp_dir:
        inventory = Path(temp_dir) / "hardware_inventory.json"
        old_manager = HardwareManager(inventory, autoload=False)
        old = Gateway()
        old.id = old.ip = "192.168.178.84"
        old.mac = "D8:85:AC:E2:59:C0"
        old_manager.add_gateway(old)
        old_manager.save_inventory(merge=False)

        manager = HardwareManager(inventory)
        current = Gateway()
        current.id = current.ip = "192.168.178.96"
        current.mac = "D8:85:AC:E2:59:C0"
        current.online = True
        manager.add_gateway(current)
        manager.save_inventory(merge=True)
        stored = json.loads(inventory.read_text(encoding="utf-8"))["gateways"]
        require(
            list(manager.gateways) == ["192.168.178.96"]
            and list(stored) == ["192.168.178.96"],
            "Alte Shelly-IP wird nur bei identischer MAC sicher aus dem Inventar ersetzt",
        )

    devices_template = (ROOT / "templates/devices.html").read_text(encoding="utf-8")
    connections = (ROOT / "templates/connections.html").read_text(encoding="utf-8")
    camera_routes = (ROOT / "routes/camera.py").read_text(encoding="utf-8")
    blu_thread = (ROOT / "threads/blu.py").read_text(encoding="utf-8")
    require(
        "GrowCam-Verbindungen" not in devices_template
        and "Kamera-Verbindungen" in connections
        and "growcam_hardware_configure" in connections
        and "/grow-control/connections/growcam/konfiguration" in camera_routes,
        "Kamera-IP und RTSP-Daten liegen vollständig auf der Seite Verbindungen",
    )
    require(
        "fresh_mqtt_vivosun_addresses" in blu_thread
        and "compact_address in mqtt_vivosun_addresses" in blu_thread,
        "BLU-Thread beendet parallele Raspberry-Abfragen bei frischer Pico-Brücke",
    )
    print("✅ Hardware-Transportbereinigung vollständig geprüft")


if __name__ == "__main__":
    main()
