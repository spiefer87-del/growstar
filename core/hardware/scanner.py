from .registry import registry


class HardwareScanner:

    def scan_gateways(self):

        print("HardwareScanner")
        print(registry.gateway_scanners_list())


        for scanner in registry.gateway_scanners_list():

            scanner.scan()


scanner = HardwareScanner()
