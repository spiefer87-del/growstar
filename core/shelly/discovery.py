from .gateway import ShellyGateway


class ShellyDiscovery:

    def __init__(self):

        self.gateways = []

    def add_gateway(self, ip):

        gateway = ShellyGateway(ip)

        if gateway.read_device_info():

            self.gateways.append(gateway)

            print(f"Gateway gefunden: {gateway.model}")

            return gateway

        return None
