import time

from core.constants import SENSOR_TIMEOUT
from core.hardware.device import HardwareDevice
from core.hardware.manager import manager
from core.hardware.scanner import scanner

from core.hardware.shelly.discovery import ShellyDiscovery
from core.hardware.vivosun import (
    LOCAL_NAME as VIVOSUN_LOCAL_NAME,
    MODEL as VIVOSUN_MODEL,
    PROTOCOL as VIVOSUN_PROTOCOL,
    device_id_from_address as vivosun_device_id,
    normalize_address as normalize_vivosun_address,
    source_id_from_address as vivosun_source_id,
    vivosun_adapter,
)
from core.sensor_sources import update_sensor_source

class HardwareService:

    def __init__(self):

        scanner.register(
            ShellyDiscovery()
        )

    # ------------------------
    # Gateway
    # ------------------------

    def gateways(self):

        return manager.gateways_list()

    def gateway(self, gateway_id):

        return manager.gateway(gateway_id)

    # ------------------------
    # Devices
    # ------------------------
    def devices(self):

        return manager.devices_list()

    def device(self, device_id):

        for device in self.devices():
    
            if device.id == device_id:
    
                return device
    
        return None

    @staticmethod
    def _vivosun_source_id(device, channel):
        props = device.properties or {}
        return vivosun_source_id(props.get("addr"), channel)

    @staticmethod
    def _vivosun_channel_label(device, channel):
        base = device.name or device.model or VIVOSUN_MODEL
        suffix = "Interner Sensor" if channel == "main" else "Externer Fuehler"
        return f"{base} · {suffix}"

    def _publish_vivosun_sensor_sources(self, device):
        props = device.properties or {}
        channels = props.get("channels") or {}
        published = {}

        for channel in ("main", "external"):
            values = channels.get(channel) or {}
            if not values.get("available"):
                continue

            observed_at = values.get("last_seen") or props.get("last_seen")
            if not observed_at:
                continue

            source_id = self._vivosun_source_id(device, channel)
            source = update_sensor_source(
                source_id,
                label=self._vivosun_channel_label(device, channel),
                source_type="hardware",
                temperature=values.get("temperature"),
                humidity=values.get("humidity"),
                rssi=props.get("rssi"),
                observed_at=observed_at,
                raw={
                    "device": device.to_dict(),
                    "channel": channel,
                },
            )
            if source is not None:
                published[channel] = source

        props["sensor_source_ids"] = {
            channel: self._vivosun_source_id(device, channel)
            for channel in published
        }
        device.properties = props
        return published

    def _device_for_bthome_component(self, gateway, component):

        # ------------------------
        # 1. Direkter Treffer über aktuelle Kopplung
        # ------------------------
    
        for device in self.devices():
    
            props = device.properties or {}
    
            if (
                props.get("gateway_id") == gateway.id
                and props.get("bthome_device_key") == component
            ):
    
                return device
    
            paired_gateways = props.get(
                "paired_gateways",
                {}
            )
    
            gateway_pair = paired_gateways.get(
                gateway.id,
                {}
            )
    
            if gateway_pair.get("bthome_device_key") == component:
    
                return device
    
    
        # ------------------------
        # 2. Adresse vom Shelly-Gateway abfragen
        # ------------------------
    
        config = gateway.get_bthome_device_config(
            component
        )
    
        addr = self._extract_addr_from_bthome_config(
            config
        )
    
        name = self._extract_name_from_bthome_config(
            config
        )
    
        device = self._find_device_by_addr(
            addr
        )
    
    
        # ------------------------
        # 3. Falls Gerät noch nicht existiert:
        #    aus Gateway-Config anlegen
        # ------------------------
    
        if device is None and addr:
    
            device = HardwareDevice()
    
            device.id = self._blu_id_from_addr(
                addr
            )
    
            device.name = name
    
            device.manufacturer = "Shelly"
    
            device.model = "Shelly BLU H&T"
    
            device.type = "sensor"
    
            device.online = True
    
            device.properties = {
                "protocol": "bthome",
                "addr": addr,
                "local_name": name,
                "model_id": 12
            }
    
            manager.add_device(
                device
            )
    
    
        if device is None:
    
            return None
    
    
        # ------------------------
        # 4. Gerät mit aktuellem Gateway verknüpfen
        # ------------------------
    
        props = device.properties
    
        component_id = gateway._bthome_component_id(
            component
        )
    
        paired_gateways = props.get(
            "paired_gateways",
            {}
        )
    
        paired_gateways[gateway.id] = {
    
            "gateway_id": gateway.id,
    
            "gateway_ip": gateway.ip,
    
            "bthome_device_key": component,
    
            "bthome_device_id": component_id,
    
            "config": config,
    
            "paired": True,
    
            "paired_at": time.time()
    
        }
    
        props["paired_gateways"] = paired_gateways
    
        props["gateway_id"] = gateway.id
        props["gateway_ip"] = gateway.ip
        props["bthome_device_key"] = component
        props["bthome_device_id"] = component_id
        props["bthome_device_config"] = config
        props["paired"] = True
    
        if addr:
    
            props["addr"] = addr
    
        if name:
    
            props["local_name"] = name
    
        return device
    
    def _blu_id_from_addr(self, addr):

        if not addr:
    
            return None
    
        clean_addr = addr.replace(
            ":",
            ""
        ).lower()
    
        return (
            "blu_" +
            clean_addr
        )
    
    
    def _find_device_by_addr(self, addr):
    
        if not addr:
    
            return None
    
        wanted = addr.lower()
    
        for device in self.devices():
    
            props = device.properties or {}
    
            current_addr = props.get(
                "addr"
            )
    
            if (
                current_addr
                and current_addr.lower() == wanted
            ):
    
                return device
    
        return None
    
    
    def _extract_addr_from_bthome_config(self, config):
    
        if not config:
    
            return None
    
        data = config
    
        if "config" in data:
    
            data = data.get(
                "config",
                {}
            )
    
        return (
            data.get("addr")
            or data.get("address")
            or data.get("mac")
        )
    
    
    def _extract_name_from_bthome_config(self, config):
    
        if not config:
    
            return "Shelly BLU"
    
        data = config
    
        if "config" in data:
    
            data = data.get(
                "config",
                {}
            )
    
        return (
            data.get("name")
            or data.get("local_name")
            or "Shelly BLU"
        )
    def _apply_bthome_sensor_updates(self, gateway):

        updated = []
    
        handled = set()
    
        updates = list(
            gateway.bluetooth_sensor_events
        )
    
        for component, update in gateway.bluetooth_known_devices.items():
    
            updates.append(
                update
            )
    
        for update in updates:
    
            component = update.get(
                "component"
            )
    
            if not component:
    
                continue
    
            key = (
                component,
                update.get("packet_id"),
                update.get("ts"),
                update.get("type")
            )
    
            if key in handled:
    
                continue
    
            handled.add(
                key
            )
    
            device = self._device_for_bthome_component(
                gateway,
                component
            )
    
            if device is None:
    
                continue
    
            props = device.properties
    
            for value_key in [
                "temperature",
                "humidity",
                "battery",
                "rssi",
                "button",
                "packet_id"
            ]:
    
                if update.get(value_key) is not None:
    
                    props[value_key] = update.get(
                        value_key
                    )
    
            last_seen = (
                update.get("last_updated_ts")
                or update.get("ts")
                or time.time()
            )
    
            props["last_seen"] = last_seen
            props["bthome_component"] = component
            props["raw_sensor_update"] = update
            props["online"] = True
    
            device.online = True

            self._publish_device_sensor_source(
                device
            )
    
            updated.append(
                device.to_dict()
            )
    
        return updated

    def _apply_known_bthome_values_to_device(self, gateway, device):

        props = device.properties or {}
    
        component = (
            props.get("bthome_device_key")
            or props.get("bthome_component")
        )
    
        if not component:
    
            return False
    
        known = gateway.bluetooth_known_devices.get(
            component
        )
    
        if not known:
    
            return False
    
        for key in [
            "temperature",
            "humidity",
            "battery",
            "rssi",
            "button",
            "packet_id"
        ]:
    
            if known.get(key) is not None:
    
                props[key] = known.get(
                    key
                )
    
        props["last_seen"] = (
            known.get("last_updated_ts")
            or known.get("ts")
            or props.get("last_seen")
            or time.time()
        )
    
        props["raw_sensor_update"] = known
        props["bthome_component"] = component
    
        device.properties = props
        device.online = True
    
        return True

    def _value_from_sensor_status(self, status):

        if not status:
    
            return None
    
        if "value" in status:
    
            return status.get(
                "value"
            )
    
        if "input" in status:
    
            return status.get(
                "input"
            )
    
        return None
    
    
    def _apply_known_objects_values(self, gateway, device, known_objects):
    
        if not known_objects:
    
            return False
    
        objects = known_objects.get(
            "objects",
            []
        )
    
        if not objects:
    
            return False
    
        props = device.properties
    
        changed = False
    
        for obj in objects:
    
            obj_id = obj.get(
                "obj_id"
            )
    
            component = obj.get(
                "component"
            )
    
            if not component:
    
                continue
    
            status = gateway.get_bthome_sensor_status(
                component
            )
    
            value = self._value_from_sensor_status(
                status
            )
    
            if value is None:
    
                continue
    
            if obj_id == 1:
    
                props["battery"] = value
    
                changed = True
    
            elif obj_id == 30:
    
                props["button"] = value
    
                changed = True
    
            elif obj_id == 46:
    
                props["humidity"] = value
    
                changed = True
    
            elif obj_id == 69:
    
                props["temperature"] = value
    
                changed = True
    
            if status.get("last_updated_ts"):
    
                props["last_seen"] = status.get(
                    "last_updated_ts"
                )
    
            props.setdefault(
                "bthome_sensor_status",
                {}
            )
    
            props["bthome_sensor_status"][component] = {
                "obj_id": obj_id,
                "status": status
            }
    
        return changed

    def _publish_device_sensor_source(self, device):

        if device is None:
    
            return None
    
        if device.type != "sensor":
    
            return None
    
        props = device.properties or {}

        if props.get("protocol") == VIVOSUN_PROTOCOL:
            published = self._publish_vivosun_sensor_sources(device)
            preferred = str(props.get("preferred_channel") or "external")
            return (
                published.get(preferred)
                or published.get("external")
                or published.get("main")
            )
    
        source_id = (
            "hardware:" +
            device.id
        )
    
        label = (
            device.name
            or props.get("local_name")
            or device.model
            or device.id
        )
    
        source = update_sensor_source(
            source_id,
            label=label,
            source_type="hardware",
            temperature=props.get("temperature"),
            humidity=props.get("humidity"),
            battery=props.get("battery"),
            rssi=props.get("rssi"),
            raw=device.to_dict()
        )
    
        props["sensor_source_id"] = source_id
    
        device.properties = props
    
        return source

    def vivosun_status(self):
        return vivosun_adapter.status()

    def scan_vivosun_devices(self, timeout=8):
        result = vivosun_adapter.scan(timeout=timeout)
        candidates = []

        for candidate in result.get("candidates") or []:
            item = dict(candidate)
            try:
                device_id = vivosun_device_id(item.get("address"))
            except Exception:
                continue

            existing = self.device(device_id)
            item["device_id"] = device_id
            item["registered"] = bool(
                existing is not None
                and (existing.properties or {}).get("protocol") == VIVOSUN_PROTOCOL
                and (existing.properties or {}).get("registered")
            )
            candidates.append(item)

        result["candidates"] = candidates
        result["count"] = len(candidates)
        return result

    def _apply_vivosun_read(self, device, result):
        props = dict(device.properties or {})
        observed_at = float(result.get("observed_at") or time.time())
        channels = {}

        for channel in ("main", "external"):
            values = dict((result.get("channels") or {}).get(channel) or {})
            values["last_seen"] = observed_at if values.get("available") else None
            channels[channel] = values

        preferred = "external" if channels.get("external", {}).get("available") else "main"
        selected = channels.get(preferred) or {}

        props.update({
            "protocol": VIVOSUN_PROTOCOL,
            "transport": "raspberry-ble",
            "addr": normalize_vivosun_address(result.get("address") or props.get("addr")),
            "local_name": result.get("name") or props.get("local_name") or VIVOSUN_LOCAL_NAME,
            "model_id": VIVOSUN_MODEL,
            "registered": True,
            "paired": True,
            "channels": channels,
            "preferred_channel": preferred,
            "temperature": selected.get("temperature"),
            "humidity": selected.get("humidity"),
            "rssi": result.get("rssi") if result.get("rssi") is not None else props.get("rssi"),
            "last_seen": observed_at,
            "last_read": time.time(),
            "last_error": None,
            "raw_status": result.get("raw_hex"),
            "measurement_source": (
                result.get("measurement_source")
                or props.get("measurement_source")
                or "gatt"
            ),
            "battery_voltage": (
                result.get("battery_voltage")
                if result.get("battery_voltage") is not None
                else props.get("battery_voltage")
            ),
            "sensor_uptime": (
                result.get("uptime_seconds")
                if result.get("uptime_seconds") is not None
                else props.get("sensor_uptime")
            ),
            "advertisement_manufacturer_id": (
                result.get("advertisement_manufacturer_id")
                if result.get("advertisement_manufacturer_id") is not None
                else props.get("advertisement_manufacturer_id")
            ),
        })

        device.name = device.name or "VIVOSUN AeroLab"
        device.manufacturer = "VIVOSUN"
        device.model = VIVOSUN_MODEL
        device.type = "sensor"
        device.online = True
        device.properties = props

        sources = self._publish_vivosun_sensor_sources(device)
        return sources

    def register_vivosun_device(self, address):
        try:
            address = normalize_vivosun_address(address)
        except Exception as exc:
            return {
                "success": False,
                "message": str(exc),
            }

        # Browserdaten allein reichen nicht: Der Kandidat muss in einem
        # frischen lokalen Scan erneut über Namen oder BLE-Signatur sichtbar sein.
        scan = self.scan_vivosun_devices(timeout=5)
        if not scan.get("success"):
            return {
                "success": False,
                "message": scan.get("error") or "VIVOSUN-Suche fehlgeschlagen.",
            }

        candidate = next(
            (
                item
                for item in scan.get("candidates") or []
                if str(item.get("address") or "").upper() == address
            ),
            None,
        )
        if candidate is None:
            return {
                "success": False,
                "message": (
                    "VS-THB1S ist nicht mehr sichtbar. "
                    "Pair/Sensor-Taste drei Sekunden druecken und erneut suchen."
                ),
            }

        read_result = vivosun_adapter.read(address)
        if not read_result.get("success"):
            return {
                "success": False,
                "message": read_result.get("error") or "VIVOSUN konnte nicht gelesen werden.",
            }

        device_id = vivosun_device_id(address)
        device = self.device(device_id) or HardwareDevice()
        device.id = device_id
        device.name = "VIVOSUN AeroLab"

        props = dict(device.properties or {})
        props["registered_at"] = props.get("registered_at") or time.time()
        device.properties = props

        sources = self._apply_vivosun_read(device, read_result)
        manager.add_device(device)
        manager.save_inventory(merge=True)

        return {
            "success": True,
            "message": "VIVOSUN VS-THB1S wurde verbunden und als Sensorquelle angelegt.",
            "device": device.to_dict(),
            "sources": sources,
        }

    def read_vivosun_sensor_values(self, device):
        props = dict(device.properties or {})
        address = props.get("addr")
        result = vivosun_adapter.read(address)
        now = time.time()

        if not result.get("success"):
            props["last_read"] = now
            props["last_error"] = result.get("error") or "VIVOSUN konnte nicht gelesen werden."
            props["last_error_at"] = now
            try:
                last_seen = float(props.get("last_seen") or 0)
            except (TypeError, ValueError):
                last_seen = 0.0
            device.online = bool(last_seen and 0 <= now - last_seen <= SENSOR_TIMEOUT)
            device.properties = props
            return {
                "success": False,
                "message": props["last_error"],
                "device": device.to_dict(),
            }

        sources = self._apply_vivosun_read(device, result)
        return {
            "success": True,
            "device": device.to_dict(),
            "sources": sources,
        }
    # ------------------------
    # Aktoren
    # ------------------------

    def actuators(self):

        return manager.actuators_list()

    # ------------------------
    # Gateway Scan
    # ------------------------

    def scan_gateways(self):

        gateways = scanner.scan_gateways()

        for gateway in gateways:

            manager.add_gateway(gateway)

        return len(gateways)

    # ------------------------
    # BLE
    # ------------------------

    def scan_ble(self):

        pass

    def get_ble_scan_result(self, gateway_id):

        gateway = manager.gateway(
            gateway_id
        )
    
        if gateway is None:
    
            return None
    
        return gateway.get_ble_scan_result()

    def register_discovered_ble_devices(self, gateway_id):

        gateway = manager.gateway(
            gateway_id
        )
    
        if gateway is None:
    
            return None
    
        registered = []
    
        for event in gateway.bluetooth_discovered:
    
            result = gateway.add_bthome_device(
                event
            )
    
            known_objects = None
    
            if result and result.get("key"):
    
                known_objects = gateway.get_bthome_device_known_objects(
                    result.get("key")
                )
    
            registered.append({
    
                "event": event,
    
                "result": result,
    
                "known_objects": known_objects
    
            })
    
        return {
    
            "count": len(
                registered
            ),
    
            "devices": registered
    
        }

    def setup_ble_sensor(self, device_id):

        device = self.device(
            device_id
        )
    
        if device is None:
    
            return None
    
        props = device.properties
    
        gateway_id = props.get(
            "gateway_id"
        )
    
        addr = props.get(
            "addr"
        )
    
        if not gateway_id or not addr:
    
            return {
                "success": False,
                "message": "Gateway oder Bluetooth-Adresse fehlt.",
                "device": device.to_dict()
            }
    
        gateway = manager.gateway(
            gateway_id
        )
    
        if gateway is None:
    
            return {
                "success": False,
                "message": "Gateway nicht gefunden.",
                "device": device.to_dict()
            }
    
        add_result = gateway.add_bthome_device_by_addr(
            addr,
            device.name
        )
    
        device_key = None
    
        if add_result:
    
            device_key = (
                add_result.get("key")
                or add_result.get("added")
                or add_result.get("component")
            )
    
        known_objects = None
    
        if device_key:
    
            known_objects = gateway.get_bthome_device_known_objects(
                device_key
            )
    
        props["bthome_device_key"] = device_key
        props["known_objects"] = known_objects
        props["setup_result"] = add_result
    
        return {
            "success": True,
            "device": device.to_dict(),
            "add_device": add_result,
            "known_objects": known_objects
        }

    def read_ble_sensor_values(self, device_id, listen=True):

        device = self.device(
            device_id
        )
    
        if device is None:
    
            return None
    
        props = device.properties

        # VIVOSUN nutzt einen direkten lokalen GATT-Read ueber den Raspberry
        # und besitzt deshalb weder Shelly-Gateway noch BTHome-Komponenten.
        # Der bestehende BLU-Thread ruft trotzdem dieselbe Service-Methode auf.
        if props.get("protocol") == VIVOSUN_PROTOCOL:
            return self.read_vivosun_sensor_values(device)
    
        gateway_id = props.get(
            "gateway_id"
        )
    
        if not gateway_id:
    
            return {
                "success": False,
                "message": "Kein Gateway beim Gerät hinterlegt.",
                "device": device.to_dict()
            }
    
        gateway = manager.gateway(
            gateway_id
        )
    
        if gateway is None:
    
            return {
                "success": False,
                "message": "Gateway nicht gefunden.",
                "device": device.to_dict()
            }
    
        # ------------------------------------------------
        # BTHome Device Key robust ermitteln
        # ------------------------------------------------
    
        device_key = (
            props.get("bthome_device_key")
            or props.get("bthome_component")
        )
    
        if not device_key:
    
            paired_gateways = props.get(
                "paired_gateways",
                {}
            )
    
            gateway_pair = paired_gateways.get(
                gateway_id,
                {}
            )
    
            device_key = gateway_pair.get(
                "bthome_device_key"
            )
    
        if not device_key and props.get("bthome_device_id") is not None:
    
            device_key = (
                "bthomedevice:" +
                str(
                    props.get("bthome_device_id")
                )
            )
    
        listen_result = None
    
        # ------------------------------------------------
        # Kurz auf neue Sensorpakete hören.
        # Nicht kritisch, wenn nichts Neues kommt.
        # ------------------------------------------------
    
        if listen:

            try:
        
                listen_result = gateway.listen_for_sensor_updates(
                    3
                )
        
            except Exception as e:
        
                print(
                    "Sensor Listener Fehler:",
                    e
                )
        
        else:
        
            listen_result = {
                "skipped": True,
                "reason": "background_update"
            }
    
        # ------------------------------------------------
        # Event-Cache übernehmen
        # ------------------------------------------------
    
        cache_applied = False
    
        try:
    
            cache_applied = self._apply_known_bthome_values_to_device(
                gateway,
                device
            )
    
        except Exception as e:
    
            print(
                "BTHome Cache Fehler:",
                e
            )
    
        props = device.properties
    
        status = None
        config = None
        known_objects = None
        sensor_values_applied = False
    
        # ------------------------------------------------
        # BTHomeDevice und BTHomeSensor Komponenten lesen
        # ------------------------------------------------
    
        if device_key:
    
            status = gateway.get_bthome_device_status(
                device_key
            )
    
            config = gateway.get_bthome_device_config(
                device_key
            )
    
            known_objects = gateway.get_bthome_device_known_objects(
                device_key
            )
    
            if known_objects:
    
                sensor_values_applied = self._apply_known_objects_values(
                    gateway,
                    device,
                    known_objects
                )
    
                props = device.properties
    
            if status:
    
                for key in [
                    "battery",
                    "rssi",
                    "last_updated_ts",
                    "packet_id"
                ]:
    
                    if status.get(key) is not None:
    
                        props[key] = status.get(
                            key
                        )
    
                if status.get("last_updated_ts"):
    
                    props["last_seen"] = status.get(
                        "last_updated_ts"
                    )
    
            props["bthome_device_key"] = device_key
            props["bthome_device_status"] = status
            props["bthome_device_config"] = config
            props["known_objects"] = known_objects
            props["paired"] = True
    
        # ------------------------------------------------
        # Falls noch raw_sensors vorhanden sind:
        # Temperatur/Luftfeuchte daraus retten
        # ------------------------------------------------
    
        # ------------------------------------------------
        # Direkten BTHome-Read als erfolgreich bestätigen
        # ------------------------------------------------
        #
        # Persistierte Geräte starten nach einem Prozess-/Raspberry-Neustart
        # absichtlich mit online=False. Ein erfolgreicher direkter Read über
        # BTHomeDevice/BTHomeSensor muss das Gerät deshalb wieder online
        # markieren. Sonst hält die Auto-Recovery den bekannten Sensor
        # fälschlich für "fehlend" und startet unnötig eine BLE-Discovery.
        #
        # Wichtig: Wir setzen hier KEIN neues last_seen. Die Sensor-Freshness
        # soll weiterhin ausschließlich von echten Sensor-Zeitstempeln kommen.

        direct_read_confirmed = bool(
            cache_applied
            or sensor_values_applied
            or status is not None
            or config is not None
            or known_objects is not None
        )

        if direct_read_confirmed:

            device.online = True
            props["online"] = True

        # Der frühere Legacy-Raw-Fallback wurde entfernt. Temperatur/Feuchte
        # werden bereits über den Event-Cache und _apply_known_objects_values()
        # normalisiert übernommen.
    
        props = device.properties
    
        props["last_read"] = time.time()

        sensor_source = self._publish_device_sensor_source(
            device
        )
    
        return {
            "success": True,
            "device": device.to_dict(),
            "device_key": device_key,
            "status": status,
            "config": config,
            "known_objects": known_objects,
            "listen": listen_result,
            "cache_applied": cache_applied,
            "sensor_values_applied": sensor_values_applied,
            "direct_read_confirmed": direct_read_confirmed,
            "sensor_source": sensor_source
        }
        
    def pair_ble_device(self, device_id, gateway_id):

        device = self.device(
            device_id
        )
    
        if device is None:
    
            return None
    
        props = device.properties
    
        addr = props.get(
            "addr"
        )
    
        if not addr:
    
            return {
                "success": False,
                "message": "Bluetooth-Adresse fehlt.",
                "device": device.to_dict()
            }
    
        gateway = manager.gateway(
            gateway_id
        )
    
        if gateway is None:
    
            return {
                "success": False,
                "message": "Gateway nicht gefunden.",
                "gateway_id": gateway_id,
                "device": device.to_dict()
            }
    
        add_result = gateway.add_bthome_device_by_addr(
            addr,
            device.name
        )
    
        device_key = None
    
        if add_result:
    
            device_key = (
                add_result.get("added")
                or add_result.get("key")
                or add_result.get("component")
            )
    
        device_component_id = None
    
        if device_key:
    
            device_component_id = gateway._bthome_component_id(
                device_key
            )
    
        known_objects = None
    
        if device_key:
    
            known_objects = gateway.get_bthome_device_known_objects(
                device_key
            )
    
        paired_gateways = props.get(
            "paired_gateways",
            {}
        )
    
        paired_gateways[gateway.id] = {
    
            "gateway_id": gateway.id,
    
            "gateway_ip": gateway.ip,
    
            "bthome_device_key": device_key,
    
            "bthome_device_id": device_component_id,
    
            "known_objects": known_objects,
    
            "setup_result": add_result,
    
            "paired": bool(device_key),
    
            "paired_at": time.time()
    
        }
    
        props["paired_gateways"] = paired_gateways
    
        props["gateway_id"] = gateway.id
        props["gateway_ip"] = gateway.ip
        props["bthome_device_key"] = device_key
        props["bthome_device_id"] = device_component_id
        props["known_objects"] = known_objects
        props["setup_result"] = add_result
        props["paired"] = bool(device_key)
    
        return {
            "success": bool(device_key),
            "message": (
                "Gerät auf diesem Gateway gekoppelt."
                if device_key
                else "Gerät konnte auf diesem Gateway nicht gekoppelt werden."
            ),
            "gateway_id": gateway.id,
            "add_device": add_result,
            "known_objects": known_objects,
            "device": device.to_dict()
        }
    
    
    def unpair_ble_device(self, device_id, gateway_id):
    
        device = self.device(
            device_id
        )
    
        if device is None:
    
            return None
    
        props = device.properties
    
        gateway = manager.gateway(
            gateway_id
        )
    
        if gateway is None:
    
            return {
                "success": False,
                "message": "Gateway nicht gefunden.",
                "gateway_id": gateway_id,
                "device": device.to_dict()
            }
    
        paired_gateways = props.get(
            "paired_gateways",
            {}
        )
    
        gateway_pair = paired_gateways.get(
            gateway.id,
            {}
        )
    
        device_key = (
            gateway_pair.get("bthome_device_key")
            or props.get("bthome_device_key")
        )
    
        delete_result = None
    
        if device_key:
    
            delete_result = gateway.delete_bthome_device(
                device_key
            )
    
        paired_gateways.pop(
            gateway.id,
            None
        )
    
        props["paired_gateways"] = paired_gateways
    
        if props.get("gateway_id") == gateway.id:
    
            for key in [
    
                "bthome_device_key",
                "bthome_device_id",
                "known_objects",
                "setup_result",
                "bthome_device_status",
                "bthome_device_config",
                "bthome_sensors",
                "temperature",
                "humidity",
                "battery"
    
            ]:
    
                props.pop(
                    key,
                    None
                )
    
            props["paired"] = False
    
        return {
            "success": True,
            "message": "Gerät auf diesem Gateway entkoppelt.",
            "gateway_id": gateway.id,
            "delete_result": delete_result,
            "device": device.to_dict()
        }
    # ------------------------
    # Refresh
    # ------------------------

    def refresh_gateway(self, gateway_id):

        gateway = self.gateway(gateway_id)

        if gateway is None:
            return None

        gateway.refresh()

        return gateway

    def refresh(self):

        print("Hardware Refresh")
    
        for gateway in self.gateways():
    
            try:
    
                self.refresh_gateway(
                    gateway.id
                )
    
            except Exception as e:
    
                print(e)

    def enable_bluetooth(self, gateway_id):
    
        gateway = manager.gateway(gateway_id)
    
        if gateway is None:
            return False
    
        return gateway.enable_bluetooth()

    def disable_bluetooth(self, gateway_id):

        gateway = manager.gateway(gateway_id)
    
        if gateway is None:
            return False
    
        return gateway.disable_bluetooth()

    def list_gateway_methods(self, gateway_id):

        gateway = manager.gateway(gateway_id)
    
        if gateway is None:
            return None
    
        return gateway.list_methods()

    def start_ble_scan(self, gateway_id):

        gateway = manager.gateway(
            gateway_id
        )
    
        if gateway is None:
    
            return None
    
        return gateway.start_device_discovery()
    
    
    def get_ble_status(self, gateway_id):
    
        gateway = manager.gateway(
            gateway_id
        )
    
        if gateway is None:
    
            return None
    
        return gateway.get_bthome_status()
    
    
    def get_ble_objects(self, gateway_id):
    
        gateway = manager.gateway(
            gateway_id
        )
    
        if gateway is None:
    
            return None
    
        return gateway.get_bthome_objects()
    
        return gateway.get_bthome_objects()

    def add_discovered_ble_devices(self, gateway_id):

        gateway = manager.gateway(
            gateway_id
        )
    
        if gateway is None:
    
            return None
    
        added = []
    
        for event in gateway.bluetooth_discovered:
    
            device = self._blu_device_from_event(
                gateway,
                event
            )
    
            if device is None:
    
                continue
    
            manager.add_device(
                device
            )
    
            added.append(
                device.to_dict()
            )
    
        updated = self._apply_bthome_sensor_updates(
            gateway
        )
    
        return {
            "count": len(added),
            "devices": added,
            "updated_count": len(updated),
            "updated": updated
        }


    def _blu_device_from_event(self, gateway, event):

        device_data = event.get(
            "device",
            {}
        )
    
        addr = device_data.get(
            "addr"
        )
    
        if not addr:
    
            return None
    
        clean_addr = addr.replace(
            ":",
            ""
        ).lower()
    
        device_id = (
            "blu_" +
            clean_addr
        )
    
        existing = self.device(
            device_id
        )
    
        old_properties = {}
    
        if existing is not None:
    
            old_properties = dict(
                existing.properties or {}
            )
    
        gateway_changed = (
            old_properties.get("gateway_id")
            and old_properties.get("gateway_id") != gateway.id
        )
    
        if gateway_changed:
    
            old_properties.pop(
                "bthome_device_key",
                None
            )
    
            old_properties.pop(
                "bthome_device_id",
                None
            )
    
            old_properties.pop(
                "known_objects",
                None
            )
    
            old_properties.pop(
                "setup_result",
                None
            )
    
            old_properties.pop(
                "bthome_device_status",
                None
            )
    
            old_properties.pop(
                "bthome_device_config",
                None
            )
    
        mfdata = device_data.get(
            "shelly_mfdata",
            {}
        )
    
        model_id = mfdata.get(
            "model_id"
        )
    
        model = "Shelly BLU"
    
        if model_id == 12:
    
            model = "Shelly BLU H&T"
    
        name = (
            device_data.get("local_name")
            or old_properties.get("local_name")
            or model
        )
    
        device = existing or HardwareDevice()
    
        device.id = device_id
    
        device.name = name
    
        device.manufacturer = "Shelly"
    
        device.model = model
    
        device.type = "sensor"
    
        device.online = True
    
        old_properties.update({
    
            "protocol": "bthome",
    
            "gateway_id": gateway.id,
    
            "gateway_ip": gateway.ip,
    
            "addr": addr,
    
            "local_name": device_data.get(
                "local_name"
            ),
    
            "rssi": device_data.get(
                "rssi"
            ),
    
            "encrypted": device_data.get(
                "encrypted",
                False
            ),
    
            "model_id": model_id,
    
            "last_seen": time.time(),
    
            "raw": event
    
        })
    
        device.properties = old_properties

        self._publish_device_sensor_source(
            device
        )
    
        return device


hardware = HardwareService()
