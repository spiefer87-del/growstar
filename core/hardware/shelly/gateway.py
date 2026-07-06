import json
import time
import threading

try:
    import websocket
except ImportError:
    websocket = None

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
        self.bluetooth_scan = {}
        self.bluetooth_events = []
        self.bluetooth_discovered = []
        self.bluetooth_scan_finished = False

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
    
    def start_device_discovery(self, duration=30):

        if not self.supports(
            "BTHome.StartDeviceDiscovery"
        ):
            return None
    
        self.bluetooth_events = []
        self.bluetooth_discovered = []
        self.bluetooth_scan_finished = False
        self.bluetooth_scanning = True
    
        listener = threading.Thread(
            target=self._listen_bthome_events,
            args=(duration + 5,),
            daemon=True
        )
    
        listener.start()
    
        time.sleep(0.5)
    
        self.api.call(
            "BTHome.StartDeviceDiscovery",
            {
                "duration": duration
            }
        )
    
        status = self.get_bthome_status()
    
        return {
            "status": status,
            "duration": duration
        }

    def get_bthome_status(self):

        if not self.supports(
            "BTHome.GetStatus"
        ):
            return None
    
        status = self.api.call(
            "BTHome.GetStatus"
        )
    
        if status:
    
            self.bluetooth_scan = status
    
            self.bluetooth_scanning = (
                "discovery" in status
            )
    
        else:
    
            self.bluetooth_scanning = False
    
        return status

    def get_bthome_objects(self):

        if not self.supports(
            "BTHome.GetObjectInfos"
        ):
            return None
    
        return self.api.call(
            "BTHome.GetObjectInfos"
        )

    def _listen_bthome_events(self, duration=35):

        if websocket is None:
    
            print(
                "WebSocket Modul fehlt. Installiere: sudo apt install python3-websocket"
            )
    
            return
    
        end_time = time.time() + duration
    
        try:
    
            ws = websocket.create_connection(
                f"ws://{self.ip}/rpc",
                timeout=5
            )
    
            ws.settimeout(1)
    
            # Wichtig:
            # Mindestens eine Anfrage mit src senden,
            # damit Shelly Notifications schickt.
            ws.send(
                json.dumps({
                    "id": 1,
                    "src": "growstar",
                    "method": "Shelly.GetStatus"
                })
            )
    
            print(
                "BLE WebSocket Listener gestartet:",
                self.ip
            )
    
            while time.time() < end_time:
    
                try:
    
                    raw = ws.recv()
    
                except Exception:
    
                    continue
    
                if not raw:
    
                    continue
    
                self._handle_bthome_event(
                    raw
                )
    
            ws.close()
    
        except Exception as e:
    
            print(
                "BLE WebSocket Fehler:",
                e
            )
    
        self.bluetooth_scanning = False
        self.bluetooth_scan_finished = True
    
        print(
            "BLE WebSocket Listener beendet:",
            self.ip
        )
    
    
    def _handle_bthome_event(self, raw):

        try:
    
            data = json.loads(
                raw
            )
    
        except Exception:
    
            data = {
                "raw": raw
            }
    
        print(
            "BLE Event:",
            data
        )
    
        self.bluetooth_events.append(
            data
        )
    
        self.bluetooth_events = self.bluetooth_events[-100:]
    
        if data.get("method") != "NotifyEvent":
    
            return
    
        params = data.get(
            "params",
            {}
        )
    
        events = params.get(
            "events",
            []
        )
    
        for event in events:
    
            component = event.get(
                "component"
            )
    
            event_name = event.get(
                "event"
            )
    
            if (
                component == "bthome"
                and event_name == "device_discovered"
            ):
    
                self.bluetooth_discovered.append(
                    event
                )
    
            if (
                component == "bthome"
                and event_name == "discovery_done"
            ):
    
                self.bluetooth_scan_finished = True
    
                self.bluetooth_scanning = False
    
    
    def get_ble_scan_result(self):

        return {
    
            "scanning": self.bluetooth_scanning,
    
            "finished": self.bluetooth_scan_finished,
    
            "device_count": len(
                self.bluetooth_discovered
            ),
    
            "events": self.bluetooth_events,
    
            "discovered": self.bluetooth_discovered
    
        }
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
