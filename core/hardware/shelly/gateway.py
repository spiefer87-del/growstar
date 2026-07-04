from core.hardware.gateway import Gateway
from .api import ShellyAPI
from .models import MODEL_NAMES


class ShellyGateway(Gateway):

    def __init__(self, ip):

        super().__init__()

        self.ip = ip

        self.api = ShellyAPI(ip)

        self.manufacturer = "Shelly"

        self.bluetooth = False

    def refresh(self):

        info = self.api.call("Shelly.GetDeviceInfo")

        if not info:

            self.online = False
            return False

        self.online = True

        self.id = self.ip

        self.model = info.get("model", "")

        self.name = MODEL_NAMES.get(
            self.model,
            self.model
        )

        self.mac = info.get("mac", "")

        self.firmware = info.get("fw_id", "")

        return True
