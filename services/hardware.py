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

        scanner.scan_gateways()

    def scan_ble(self):

        pass

    def refresh(self):

        pass


hardware = HardwareService()
