class HardwareScanner:

    def __init__(self):

        self.scanners = []

    def register(self, scanner):

        self.scanners.append(scanner)

    def scan_gateways(self):

        print(f"{len(self.scanners)} Gateway-Scanner registriert")

        for scanner in self.scanners:

            scanner.scan()


scanner = HardwareScanner()
