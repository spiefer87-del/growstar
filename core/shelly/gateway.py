from .api import ShellyAPI


class ShellyGateway:

    def __init__(self, ip):

        self.ip = ip
        self.api = ShellyAPI(ip)

        self.model = None
        self.firmware = None

    def read_device_info(self):

        data = self.api.rpc("Shelly.GetDeviceInfo")

        if not data:
            return False

        self.model = data.get("model")
        self.firmware = data.get("fw_id")

        return True

    def read_config(self):

        return self.api.rpc("Shelly.GetConfig")

    def enable_ble(self):

        config = self.read_config()

        if not config:
            return False

        print("BLE-Konfiguration gelesen")

        #
        # Hier ergänzen wir später die RPC-Aufrufe,
        # sobald wir die genaue Firmware kennen.
        #

        return True
