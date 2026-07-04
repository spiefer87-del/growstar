from core.hardware.manager import manager
from core.hardware.scanner import scanner

from core.hardware.shelly.discovery import ShellyDiscovery


class HardwareService:

    def __init__(self):

        scanner.register(
            ShellyDiscovery()
        )

    def gateway(self, gateway_id):

        return manager.gateway(gateway_id)

    def gateways(self):

        return manager.gateways_list()

    def devices(self):

        return manager.devices_list()

    def actuators(self):

        return manager.actuators_list()

    def scan_gateways(self):

        gateways = scanner.scan_gateways()

        for gateway in gateways:

            manager.add_gateway(gateway)

        return len(gateways)

    def scan_ble(self):

        pass

    def refresh_gateway(self, gateway_id):

        gateway = self.gateway(gateway_id)
    
        if gateway is None:
            return None
    
        gateway.refresh()
    
        return gateway
    
    def refresh(self):

        for gateway in self.gateways():
    
            try:
    
                gateway.refresh()
    
            except Exception as e:
    
                print(e)


hardware = HardwareService()
