from core.hardware.registry import registry

registry.register_gateway_scanner(
    ShellyDiscovery()
)

class ShellyDiscovery:

    def scan(self):

        print("Shelly Discovery gestartet")
