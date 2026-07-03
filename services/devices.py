from core.devices.manager import manager

from core.devices.shelly.discovery import ShellyDiscovery


class DeviceService:

    def __init__(self):

        self.discovery = ShellyDiscovery()

    def add_shelly(self, ip):

        return self.discovery.add(ip)

    def devices(self):

        return manager.all()


service = DeviceService()
