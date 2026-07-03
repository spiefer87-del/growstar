from typing import Dict
from .models import Device


class HardwareManager:

    def __init__(self):

        self.devices: Dict[str, Device] = {}

    def add(self, device: Device):

        self.devices[device.id] = device

    def remove(self, device_id):

        self.devices.pop(device_id, None)

    def get(self, device_id):

        return self.devices.get(device_id)

    def all(self):

        return list(self.devices.values())

    def clear(self):

        self.devices.clear()

    def count(self):

        return len(self.devices)


manager = HardwareManager()
