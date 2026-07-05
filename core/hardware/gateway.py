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

        self.bluetooth_enabled = False

        self.bluetooth_scanning = False

        self.bluetooth_scan = {}

        self.rssi = None

        self.uptime = None

        self.methods = []

        self.capabilities = {}


    def to_dict(self):

        data = super().to_dict()

        data.update({

            "ip": self.ip,

            "mac": self.mac,

            "firmware": self.firmware,

            "bluetooth": self.bluetooth,

            "bluetooth_enabled": self.bluetooth_enabled,

            "bluetooth_scanning": self.bluetooth_scanning,

            "bluetooth_scan": self.bluetooth_scan,

            "rssi": self.rssi,

            "uptime": self.uptime,

            "methods": self.methods,

            "capabilities": self.capabilities

        })

        return data


    def supports(self, method):

        if not self.methods:

            return False

        return method in self.methods
