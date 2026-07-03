from core.hardware.manager import manager


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

        """
        Netzwerk nach Gateways durchsuchen.
        """
        pass

    def scan_ble(self):

        """
        Über vorhandene Gateways nach BLE-Geräten suchen.
        """
        pass


hardware = HardwareService()
