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
