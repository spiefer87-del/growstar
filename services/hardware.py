from core.hardware.manager import manager
from core.hardware.shelly.discovery import ShellyDiscovery


class HardwareService:

    def __init__(self):

        self.discovery = ShellyDiscovery()

    def discover_shelly(self, ip):

        return self.discovery.add(ip)

    def devices(self):

        return manager.all()


hardware = HardwareService()
