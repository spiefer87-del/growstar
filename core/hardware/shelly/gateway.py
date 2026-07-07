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
        self.bluetooth_sensor_events = []
        self.bluetooth_known_devices = {}

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
    
    def start_device_discovery(self, duration=60):

        if not self.supports(
            "BTHome.StartDeviceDiscovery"
        ):
            return None
    
        # --------------------------
        # Bluetooth vor Scan aktivieren
        # --------------------------
    
        ble = self.get_ble_config()
    
        if ble and not ble.get(
            "enable",
            False
        ):
    
            print(
                "Bluetooth ist deaktiviert. Aktiviere Bluetooth..."
            )
    
            self.enable_bluetooth()
    
            time.sleep(
                2
            )
    
        # --------------------------
        # Scan vorbereiten
        # --------------------------
    
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
    
        time.sleep(
            0.5
        )
    
        # --------------------------
        # Discovery starten
        # --------------------------
    
        self.api.call(
            "BTHome.StartDeviceDiscovery",
            {
                "duration": duration
            }
        )
    
        status = self.get_bthome_status()
    
        return {
            "status": status,
            "duration": duration,
            "gateway": {
                "id": self.id,
                "ip": self.ip,
                "name": self.name
            }
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


        # --------------------------
        # Status von bereits gekoppelten
        # BTHome Devices auswerten
        # --------------------------

        if data.get("method") == "NotifyStatus":

            params = data.get(
                "params",
                {}
            )

            ts = params.get(
                "ts",
                time.time()
            )

            for component, payload in params.items():

                if (
                    isinstance(component, str)
                    and component.startswith("bthomedevice:")
                ):

                    self._handle_bthome_device_status(
                        component,
                        payload,
                        ts
                    )

            return


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


            # --------------------------
            # Neues Gerät während Discovery
            # --------------------------

            if (
                component == "bthome"
                and event_name == "device_discovered"
            ):

                self.bluetooth_discovered.append(
                    event
                )


            # --------------------------
            # Discovery beendet
            # --------------------------

            if (
                component == "bthome"
                and event_name == "discovery_done"
            ):

                self.bluetooth_scan_finished = True

                self.bluetooth_scanning = False


            # --------------------------
            # Bereits gekoppeltes Gerät
            # liefert Sensordaten
            # --------------------------

            if (
                isinstance(component, str)
                and component.startswith("bthomedevice:")
            ):

                self._handle_bthome_device_event(
                    event
                )
    
    
        def get_ble_scan_result(self):

            return {
    
                "scanning": self.bluetooth_scanning,
    
                "finished": self.bluetooth_scan_finished,
    
                "device_count": len(
                    self.bluetooth_discovered
                ),
    
                "sensor_event_count": len(
                    self.bluetooth_sensor_events
                ),
    
                "events": self.bluetooth_events,
    
                "discovered": self.bluetooth_discovered,
    
                "sensor_events": self.bluetooth_sensor_events,
    
                "known_devices": self.bluetooth_known_devices
    
            }

    def add_bthome_device(self, event):

        device_data = event.get(
            "device",
            {}
        )
    
        addr = device_data.get(
            "addr"
        )
    
        if not addr:
    
            return None
    
        name = device_data.get(
            "local_name",
            "Shelly BLU"
        )
    
        mfdata = device_data.get(
            "shelly_mfdata",
            {}
        )
    
        result = self.api.call(
            "BTHome.AddDevice",
            {
                "config": {
                    "addr": addr,
                    "name": name,
                    "meta": {
                        "manufacturer": "Shelly",
                        "model_id": mfdata.get(
                            "model_id"
                        ),
                        "local_name": name
                    }
                }
            }
        )
    
        print(
            "BTHome.AddDevice Result:",
            result
        )
    
        return result

    def get_bthome_device_known_objects(self, key):

        if not self.supports(
            "BTHomeDevice.GetKnownObjects"
        ):

            return None

        device_id = self._bthome_component_id(
            key
        )

        if device_id is None:

            return None

        return self.api.call(
            "BTHomeDevice.GetKnownObjects",
            {
                "id": device_id
            }
        )
        
    def _bthome_component_id(self, key):

        if key is None:

            return None

        if isinstance(
            key,
            int
        ):

            return key

        try:

            text = str(
                key
            )

            if ":" in text:

                text = text.split(
                    ":"
                )[-1]

            return int(
                text
            )

        except Exception:

            return None

    def _sensor_value(self, sensors, obj_id):

        items = sensors.get(
            str(obj_id),
            []
        )

        if not items:

            return None

        if not isinstance(
            items,
            list
        ):

            return None

        if len(items) == 0:

            return None

        return items[0].get(
            "value"
        )


    def _values_from_bthome_sensors(self, sensors):

        values = {}

        battery = self._sensor_value(
            sensors,
            1
        )

        humidity = self._sensor_value(
            sensors,
            46
        )

        temperature = self._sensor_value(
            sensors,
            69
        )

        button = self._sensor_value(
            sensors,
            30
        )

        if battery is not None:

            values["battery"] = battery

        if humidity is not None:

            values["humidity"] = humidity

        if temperature is not None:

            values["temperature"] = temperature

        if button is not None:

            values["button"] = button

        values["raw_sensors"] = sensors

        return values


    def _store_bthome_sensor_update(self, update):

        component = update.get(
            "component"
        )

        if not component:

            return

        old = self.bluetooth_known_devices.get(
            component,
            {}
        )

        old.update(
            update
        )

        self.bluetooth_known_devices[component] = old

        self.bluetooth_sensor_events.append(
            update
        )

        self.bluetooth_sensor_events = self.bluetooth_sensor_events[-100:]


    def _handle_bthome_device_status(self, component, payload, ts=None):

        if not isinstance(
            payload,
            dict
        ):

            return

        update = {
            "component": component,
            "component_id": self._bthome_component_id(
                component
            ),
            "ts": ts or time.time(),
            "type": "status"
        }

        for key in [
            "battery",
            "rssi",
            "last_updated_ts",
            "packet_id"
        ]:

            if key in payload and payload.get(key) is not None:

                update[key] = payload.get(
                    key
                )

        self._store_bthome_sensor_update(
            update
        )


    def _handle_bthome_device_event(self, event):

        component = event.get(
            "component"
        )

        sensors = event.get(
            "sensors",
            {}
        )

        values = self._values_from_bthome_sensors(
            sensors
        )

        update = {
            "component": component,
            "component_id": self._bthome_component_id(
                component
            ),
            "event": event.get(
                "event"
            ),
            "ts": event.get(
                "ts",
                time.time()
            ),
            "type": "event"
        }

        update.update(
            values
        )

        self._store_bthome_sensor_update(
            update
        )


    def get_bthome_device_status(self, key):

        if not self.supports(
            "BTHomeDevice.GetStatus"
        ):

            return None

        device_id = self._bthome_component_id(
            key
        )

        if device_id is None:

            return None

        return self.api.call(
            "BTHomeDevice.GetStatus",
            {
                "id": device_id
            }
        )


    def get_bthome_device_config(self, key):

        if not self.supports(
            "BTHomeDevice.GetConfig"
        ):

            return None

        device_id = self._bthome_component_id(
            key
        )

        if device_id is None:

            return None

        return self.api.call(
            "BTHomeDevice.GetConfig",
            {
                "id": device_id
            }
        )

    def delete_bthome_device(self, key):

        if not self.supports(
            "BTHome.DeleteDevice"
        ):
    
            return None
    
        device_id = self._bthome_component_id(
            key
        )
    
        if device_id is None:
    
            return None
    
        result = self.api.call(
            "BTHome.DeleteDevice",
            {
                "id": device_id
            }
        )
    
        print(
            "BTHome.DeleteDevice Result:",
            result
        )
    
        return result
    # --------------------------
    # BTHome Sensor Setup
    # --------------------------
    
    def add_bthome_device_by_addr(self, addr, name=None):
    
        if not self.supports(
            "BTHome.AddDevice"
        ):
            return None
    
        if not addr:
    
            return None
    
        config = {
            "addr": addr
        }
    
        if name:
    
            config["name"] = name
    
        result = self.api.call(
            "BTHome.AddDevice",
            {
                "config": config
            }
        )
    
        print(
            "BTHome.AddDevice by addr Result:",
            result
        )
    
        return result
    
    
    def get_bthome_device_known_objects_by_id(self, device_id):
    
        if not self.supports(
            "BTHomeDevice.GetKnownObjects"
        ):
            return None
    
        return self.api.call(
            "BTHomeDevice.GetKnownObjects",
            {
                "id": device_id
            }
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
