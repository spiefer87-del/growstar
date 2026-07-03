from core.hardware.manager import manager
from core.hardware.shelly.discovery import ShellyDiscovery


class HardwareService:

    def __init__(self):

        self.discovery = ShellyDiscovery()

    def discover_shelly(self, ip):

        return self.discovery.add(ip)

    def devices(self):

        return manager.all()


hardware = HardwareService()

from core.hardware.models import Device

    demo = Device()
    
    demo.id = "demo"
    
    demo.name = "Shelly Plug S"
    
    demo.model = "SNPL-00112EU"
    
    demo.ip = "192.168.178.60"
    
    demo.online = True
    
    manager.add(demo)
