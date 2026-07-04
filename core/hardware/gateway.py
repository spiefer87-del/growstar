from .device import HardwareDevice
from .types import GATEWAY


class Gateway(HardwareDevice):

    def __init__(self):

        super().__init__()

        self.type = GATEWAY

        self.ip = ""

        self.mac = ""

        self.firmware = ""

        self.bluetooth = False

        self.rssi = None

        self.uptime = None


    def to_dict(self):

        return {

            "id": self.id,

            "name": self.name,

            "type": self.type,

            "manufacturer": self.manufacturer,

            "model": self.model,

            "ip": self.ip,

            "mac": self.mac,

            "online": self.online,

            "firmware": self.firmware,

            "bluetooth": self.bluetooth,

            "rssi": self.rssi,

            "uptime": self.uptime

        }
