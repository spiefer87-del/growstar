from core.devices.models import Device

from .api import ShellyAPI


class ShellyGateway(Device):

    def __init__(self, ip):

        super().__init__()

        self.ip = ip

        self.manufacturer = "Shelly"

        self.api = ShellyAPI(ip)

    def refresh(self):

        info = self.api.device_info()

        if not info:

            self.online = False

            return False

        self.online = True

        self.id = info.get("mac", self.ip)

        self.name = info.get("name", "")

        self.model = info.get("model", "")

        self.mac = info.get("mac", "")

        self.firmware = info.get("fw_id", "")

        config = self.api.config()

        if config:

            self.properties["bluetooth"] = config.get(
                "ble",
                {}
            ).get(
                "enable",
                False
            )

        return True
