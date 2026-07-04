from core.hardware.gateway import Gateway


class ShellyGateway(Gateway):

    def __init__(self, ip):

        super().__init__()

        self.ip = ip

        self.manufacturer = "Shelly"

        self.bluetooth = True

        self.online = False
