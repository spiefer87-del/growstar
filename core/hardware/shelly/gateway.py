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
    def build_capabilities(self):

        self.capabilities = {

            # Bluetooth
            "ble": self.supports("BLE.GetStatus"),
            "ble_config": self.supports("BLE.SetConfig"),
            "ble_pairing": self.supports("BLE.StartPairing"),
        
            # BTHome
            "bthome": self.supports("BTHome.GetStatus"),
            "bthome_discovery": self.supports("BTHome.StartDeviceDiscovery"),
            "bthome_learning": self.supports("BTHomeControl.StartLearning"),
        
            # Matter
            "matter": self.supports("Matter.GetStatus"),
        
            # KNX
            "knx": self.supports("KNX.GetStatus"),
        
            # Scripts
            "scripts": self.supports("Script.List"),
        
            # Scheduler
            "schedule": self.supports("Schedule.List"),
        
            # WLAN
            "wifi_scan": self.supports("Wifi.Scan"),
        
            # OTA
            "ota": self.supports("OTA.Update"),
        
            # Switch
            "switch": self.supports("Switch.Toggle"),
        
            # Cloud
            "cloud": self.supports("Cloud.GetStatus")
        }
    
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

        if not self.methods:

            methods = self.list_methods()
        
            if methods:
        
                self.methods = methods.get(
                    "methods",
                    []
                )
        
                self.build_capabilities()

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
    # BTHome Discovery
    # --------------------------
    
    def start_device_discovery(self):

        if not self.supports(
            "BTHome.StartDeviceDiscovery"
        ):
            return None
    
        self.api.call(
            "BTHome.StartDeviceDiscovery"
        )
    
        return self.get_bthome_status()

    def get_bthome_status(self):

        if not self.supports(
            "BTHome.GetStatus"
        ):
            return None
    
        return self.api.call(
            "BTHome.GetStatus"
        )

    def get_bthome_objects(self):

        if not self.supports(
            "BTHome.GetObjectInfos"
        ):
            return None
    
        return self.api.call(
            "BTHome.GetObjectInfos"
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
