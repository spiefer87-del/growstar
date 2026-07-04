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

        self.rssi = None
        self.uptime = None


    # --------------------------
    # Gerät aktualisieren
    # --------------------------

    # --------------------------
    # Gerät aktualisieren
    # --------------------------

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

        # --------------------------
        # Status laden
        # --------------------------

        status = self.get_status()

        if status:

            wifi = status.get("wifi", {})

            self.rssi = wifi.get("rssi")

            self.uptime = status.get(
                "sys",
                {}
            ).get("uptime")

        # --------------------------
        # BLE Konfiguration laden
        # --------------------------

        ble = self.get_ble_config()

        if ble:
        
            self.bluetooth = True
        
            self.bluetooth_enabled = ble.get(
                "enable",
                False
            )
        
        else:
        
            self.bluetooth = False
        
            self.bluetooth_enabled = False

        return True

    # --------------------------
    # Shelly Status
    # --------------------------

    def get_status(self):

        return self.api.call(
            "Shelly.GetStatus"
        )

    def get_ble_config(self):

        return self.api.call(
            "BLE.GetConfig"
        )

    # --------------------------
    # Bluetooth Setup
    # --------------------------

    def enable_bluetooth(self):

        result = self.api.call(
            "BLE.SetConfig",
            {
                "config": {
                    "enable": True
                }
            }
        )
    
        self.refresh()
    
        return result
    
    def disable_bluetooth(self):

        result = self.api.call(
            "BLE.SetConfig",
            {
                "config": {
                    "enable": False
                }
            }
        )
    
        self.refresh()
    
        return result

    def list_methods(self):

        return self.api.list_methods()
