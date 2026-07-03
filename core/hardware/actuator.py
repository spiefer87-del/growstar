from .device import HardwareDevice

from .types import ACTUATOR


class Actuator(HardwareDevice):

    def __init__(self):

        super().__init__()

        self.type = ACTUATOR
