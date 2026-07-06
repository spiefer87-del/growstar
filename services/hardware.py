import time

from core.hardware.device import HardwareDevice
from core.hardware.manager import manager
from core.hardware.scanner import scanner

from core.hardware.shelly.discovery import ShellyDiscovery


class HardwareService:

    def __init__(self):

        scanner.register(
            ShellyDiscovery()
        )

    # ------------------------
    # Gateway
    # ------------------------

    def gateways(self):

        return manager.gateways_list()

    def gateway(self, gateway_id):

        return manager.gateway(gateway_id)

    # ------------------------
    # Devices
    # ------------------------

    def devices(self):

        return manager.devices_list()

    # ------------------------
    # Aktoren
    # ------------------------

    def actuators(self):

        return manager.actuators_list()

    # ------------------------
    # Gateway Scan
    # ------------------------

    def scan_gateways(self):

        gateways = scanner.scan_gateways()

        for gateway in gateways:

            manager.add_gateway(gateway)

        return len(gateways)

    # ------------------------
    # BLE
    # ------------------------

    def scan_ble(self):

        pass

    def get_ble_scan_result(self, gateway_id):

        gateway = manager.gateway(
            gateway_id
        )
    
        if gateway is None:
    
            return None
    
        return gateway.get_ble_scan_result()

    def register_discovered_ble_devices(self, gateway_id):

        gateway = manager.gateway(
            gateway_id
        )
    
        if gateway is None:
    
            return None
    
        registered = []
    
        for event in gateway.bluetooth_discovered:
    
            result = gateway.add_bthome_device(
                event
            )
    
            known_objects = None
    
            if result and result.get("key"):
    
                known_objects = gateway.get_bthome_device_known_objects(
                    result.get("key")
                )
    
            registered.append({
    
                "event": event,
    
                "result": result,
    
                "known_objects": known_objects
    
            })
    
        return {
    
            "count": len(
                registered
            ),
    
            "devices": registered
    
        }

    # ------------------------
    # Refresh
    # ------------------------

    def refresh_gateway(self, gateway_id):

        gateway = self.gateway(gateway_id)

        if gateway is None:
            return None

        gateway.refresh()

        return gateway

    def refresh(self):

        print("Hardware Refresh")
    
        for gateway in self.gateways():
    
            try:
    
                self.refresh_gateway(
                    gateway.id
                )
    
            except Exception as e:
    
                print(e)

    def enable_bluetooth(self, gateway_id):
    
        gateway = manager.gateway(gateway_id)
    
        if gateway is None:
            return False
    
        return gateway.enable_bluetooth()

    def disable_bluetooth(self, gateway_id):

        gateway = manager.gateway(gateway_id)
    
        if gateway is None:
            return False
    
        return gateway.disable_bluetooth()

    def list_gateway_methods(self, gateway_id):

        gateway = manager.gateway(gateway_id)
    
        if gateway is None:
            return None
    
        return gateway.list_methods()

    def start_ble_scan(self, gateway_id):

        gateway = manager.gateway(
            gateway_id
        )
    
        if gateway is None:
    
            return None
    
        return gateway.start_device_discovery()
    
    
    def get_ble_status(self, gateway_id):
    
        gateway = manager.gateway(
            gateway_id
        )
    
        if gateway is None:
    
            return None
    
        return gateway.get_bthome_status()
    
    
    def get_ble_objects(self, gateway_id):
    
        gateway = manager.gateway(
            gateway_id
        )
    
        if gateway is None:
    
            return None
    
        return gateway.get_bthome_objects()
    
        return gateway.get_bthome_objects()

    def add_discovered_ble_devices(self, gateway_id):

        gateway = manager.gateway(
            gateway_id
        )
    
        if gateway is None:
    
            return None
    
        added = []
    
        for event in gateway.bluetooth_discovered:
    
            device = self._blu_device_from_event(
                gateway,
                event
            )
    
            if device is None:
    
                continue
    
            manager.add_device(
                device
            )
    
            added.append(
                device.to_dict()
            )
    
        return {
            "count": len(added),
            "devices": added
        }


    def _blu_device_from_event(self, gateway, event):
    
        device_data = event.get(
            "device",
            {}
        )
    
        addr = device_data.get(
            "addr"
        )
    
        if not addr:
    
            return None
    
        clean_addr = addr.replace(
            ":",
            ""
        ).lower()
    
        mfdata = device_data.get(
            "shelly_mfdata",
            {}
        )
    
        model_id = mfdata.get(
            "model_id"
        )
    
        model = "Shelly BLU"
    
        if model_id == 12:
    
            model = "Shelly BLU H&T"
    
        name = device_data.get(
            "local_name"
        ) or model
    
        device = HardwareDevice()
    
        device.id = (
            "blu_" +
            clean_addr
        )
    
        device.name = name
    
        device.manufacturer = "Shelly"
    
        device.model = model
    
        device.type = "sensor"
    
        device.online = True
    
        device.properties = {
    
            "protocol": "bthome",
    
            "gateway_id": gateway.id,
    
            "gateway_ip": gateway.ip,
    
            "addr": addr,
    
            "local_name": device_data.get(
                "local_name"
            ),
    
            "rssi": device_data.get(
                "rssi"
            ),
    
            "encrypted": device_data.get(
                "encrypted",
                False
            ),
    
            "model_id": model_id,
    
            "last_seen": time.time(),
    
            "raw": event
    
        }
    
        return device


hardware = HardwareService()
