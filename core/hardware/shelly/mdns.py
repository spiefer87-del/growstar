import socket
import time

from zeroconf import Zeroconf, ServiceBrowser, ServiceListener


class ShellyListener(ServiceListener):

    def __init__(self):

        self.devices = []

    def add_service(self, zc, service_type, name):

        info = zc.get_service_info(service_type, name)

        if not info:
            return

        addresses = info.parsed_addresses()

        if not addresses:
            return

        ip = addresses[0]

        print(f"Shelly gefunden: {name} ({ip})")

        self.devices.append({
            "name": name,
            "ip": ip
        })

    def update_service(self, zc, service_type, name):
        pass

    def remove_service(self, zc, service_type, name):
        pass


class ShellyMDNS:

    def scan(self):

        print("mDNS Suche...")

        zc = Zeroconf()

        listener = ShellyListener()

        ServiceBrowser(
            zc,
            "_http._tcp.local.",
            listener
        )

        time.sleep(3)

        zc.close()

        return listener.devices
