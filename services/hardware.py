from core.hardware.manager import manager
from core.hardware.shelly.discovery import ShellyDiscovery


class HardwareService:

    def __init__(self):

        self.discovery = ShellyDiscovery()

    def scan(self):

        #
        # Hier suchen wir später
        #

        pass

    def devices(self):

        return manager.all()

    def count(self):

        return manager.count()


hardware = HardwareService()
