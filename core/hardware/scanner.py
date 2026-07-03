class HardwareScanner:

    def __init__(self):
        self.scanners = []

    def register(self, scanner):
        self.scanners.append(scanner)

    def scan_gateways(self):

        gateways = []

        print(f"{len(self.scanners)} Scanner gestartet")

        for scanner in self.scanners:

            found = scanner.scan()

            if found:
                gateways.extend(found)

        return gateways


scanner = HardwareScanner()
