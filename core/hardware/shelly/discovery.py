class ShellyDiscovery:

    def scan(self):

        print(">>> Shelly Discovery")

        gateways = []

        gateways.extend(
            self.scan_mdns()
        )

        if not gateways:

            gateways.extend(
                self.scan_network()
            )

        return gateways

    def scan_mdns(self):

        print("  -> mDNS Suche")

        return []

    def scan_network(self):

        print("  -> Netzwerk Scan")

        return []
