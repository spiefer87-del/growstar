from .gateway import ShellyGateway


class ShellyDiscovery:

    def __init__(self):

        self.devices = {}

    def add(self, ip):

        gateway = ShellyGateway(ip)

        if gateway.refresh():

            self.devices[ip] = gateway

            return gateway

        return None

    def all(self):

        return list(self.devices.values())
