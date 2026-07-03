from core.hardware.manager import manager
from core.hardware.scanner import scanner


class HardwareService:

    def gateways(self):

        return manager.gateways_list()

    def devices(self):

        return manager.devices_list()

    def actuators(self):

        return manager.actuators_list()

    def refresh(self):

        """
        Wird später alle Hardware aktualisieren.
        """
        pass

    def scan_gateways(self):

        print("HardwareService.scan_gateways()")
    
        scanner.scan_gateways()

    def scan_ble(self):

        """
        Über vorhandene Gateways nach BLE-Geräten suchen.
        """
        pass


hardware = HardwareService()
