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

        data = super().to_dict()

        data.update({

            "ip": self.ip,

            "mac": self.mac,

            "firmware": self.firmware,

            "bluetooth": self.bluetooth,

            "rssi": self.rssi,

            "uptime": self.uptime

        })

        return data
