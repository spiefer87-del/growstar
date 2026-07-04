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

        # ← HIER kommt Schritt 3 ins Spiel
        status = self.get_status()

        if status:
        
            ble = status.get("ble", {})
            bthome = status.get("bthome", {})
        
            # Dieses Gateway besitzt Bluetooth
            self.bluetooth = (
                "ble" in status or
                "bthome" in status
            )
        
            errors = bthome.get("errors", [])
        
            self.bluetooth_enabled = (
                "bluetooth_disabled" not in errors
            )
        
            wifi = status.get("wifi", {})
            self.rssi = wifi.get("rssi")
        
            self.uptime = status.get("sys", {}).get("uptime")

        return True


    # --------------------------
    # Shelly Status
    # --------------------------

    def get_status(self):

        return self.api.call(
            "Shelly.GetStatus"
        )

    # --------------------------
    # Bluetooth Setup
    # --------------------------

    def enable_bluetooth(self):

        return self.api.call(
    
            "BLE.SetConfig",
    
            {
                "config": {
                    "enable": True
                }
            }
    
        )
    
    def disable_bluetooth(self):

        return self.api.call(
    
            "BLE.SetConfig",
    
            {
                "config": {
                    "enable": False
                }
            }
    
        )

    def list_methods(self):

        return self.api.list_methods()
