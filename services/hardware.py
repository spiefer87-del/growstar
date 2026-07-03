from core.hardware.manager import manager
from core.hardware.scanner import scanner

from core.hardware.shelly.discovery import ShellyDiscovery


class HardwareService:

    def __init__(self):

        scanner.register(
            ShellyDiscovery()
        )

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

    def refresh(self):

        pass


hardware = HardwareService()
