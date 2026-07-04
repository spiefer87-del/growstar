from .mdns import ShellyMDNS
from .network import ShellyNetwork
from .gateway import ShellyGateway


class ShellyDiscovery:

    def __init__(self):

        self.mdns = ShellyMDNS()
        self.network = ShellyNetwork()

    def scan(self):

        print(">>> Shelly Discovery")

        gateways = []

        for device in self.mdns.scan():

            if "shelly" in device["name"].lower():
        
                gateway = ShellyGateway(
                    device["ip"]
                )
        
                gateway.id = device["ip"]
        
                gateway.name = device["name"]
        
                gateways.append(gateway)

        if not gateways:

            gateways.extend(
                self.network.scan()
            )

        return gateways
