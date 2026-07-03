from .mdns import ShellyMDNS
from .network import ShellyNetwork


class ShellyDiscovery:

    def __init__(self):

        self.mdns = ShellyMDNS()

        self.network = ShellyNetwork()

    def scan(self):

        gateways = []

        gateways.extend(
            self.mdns.scan()
        )

        if not gateways:

            gateways.extend(
                self.network.scan()
            )

        return gateways
