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


hardware = HardwareService()
