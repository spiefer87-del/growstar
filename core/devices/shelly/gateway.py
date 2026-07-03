from .api import ShellyAPI


class ShellyGateway:

    def __init__(self, ip):

        self.ip = ip
        self.api = ShellyAPI(ip)

        self.online = False

        self.name = ""
        self.model = ""
        self.mac = ""
        self.firmware = ""

        self.bluetooth = False

    def refresh(self):

        info = self.api.get_device_info()

        if not info:
            self.online = False
            return False

        self.online = True

        self.name = info.get("name", "")
        self.model = info.get("model", "")
        self.mac = info.get("mac", "")
        self.firmware = info.get("fw_id", "")

        config = self.api.get_config()

        if config:

            ble = config.get("ble", {})

            self.bluetooth = ble.get("enable", False)

        return True
