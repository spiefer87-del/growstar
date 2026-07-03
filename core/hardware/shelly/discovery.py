from .mdns import ShellyMDNS
from .network import ShellyNetwork


class ShellyDiscovery:

    def __init__(self):

        self.mdns = ShellyMDNS()
        self.network = ShellyNetwork()

    def scan(self):

        print(">>> Shelly Discovery")

        gateways = []

        for device in self.mdns.scan():

            if "shelly" in device["name"].lower():

                print(f"✔ Shelly erkannt: {device['ip']}")

                gateways.append(device)

        if not gateways:

            gateways.extend(
                self.network.scan()
            )

        return gateways
