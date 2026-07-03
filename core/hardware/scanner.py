from .registry import registry


class HardwareScanner:

    def scan_gateways(self):

        for scanner in registry.gateway_scanners_list():

            scanner.scan()


scanner = HardwareScanner()
