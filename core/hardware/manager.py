class HardwareManager:

    def __init__(self):

        self.gateways = {}

        self.devices = {}

        self.actuators = {}

    # ---------- Gateways ----------

    def add_gateway(self, gateway):

        self.gateways[gateway.id] = gateway

    def gateways_list(self):

        return list(self.gateways.values())

    def gateway(self, gateway_id):

        return self.gateways.get(gateway_id)

    # ---------- Geräte ----------

    def add_device(self, device):

        self.devices[device.id] = device

    def devices_list(self):

        return list(self.devices.values())

    # ---------- Aktoren ----------

    def add_actuator(self, actuator):

        self.actuators[actuator.id] = actuator

    def actuators_list(self):

        return list(self.actuators.values())

    # ---------- Allgemein ----------

    def clear(self):

        self.gateways.clear()

        self.devices.clear()

        self.actuators.clear()


manager = HardwareManager()
