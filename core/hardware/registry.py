class HardwareRegistry:

    def __init__(self):

        self.gateway_scanners = []

    def register_gateway_scanner(self, scanner):

        self.gateway_scanners.append(scanner)

    def gateway_scanners_list(self):

        return self.gateway_scanners


registry = HardwareRegistry()
