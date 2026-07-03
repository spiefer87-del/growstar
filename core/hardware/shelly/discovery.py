from core.hardware.manager import manager

from .gateway import ShellyGateway


class ShellyDiscovery:

    def add(self, ip):

        gateway = ShellyGateway(ip)

        if gateway.refresh():

            manager.add(gateway)

            return gateway

        return None
