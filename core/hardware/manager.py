from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading

from .device import HardwareDevice
from .gateway import Gateway


INVENTORY_VERSION = 1


def _default_inventory_path():
    env_path = os.getenv("GROWSTAR_HARDWARE_INVENTORY")
    if env_path:
        return Path(env_path).expanduser().resolve()

    project_root = Path(__file__).resolve().parents[2]
    return project_root / "instance" / "hardware_inventory.json"


class HardwareManager:
    """Thread-sicherer In-Memory-Hardwarebestand mit persistenter Recovery-Kopie.

    Die Laufzeitobjekte bleiben weiterhin die Quelle für den aktuellen Zustand.
    Die JSON-Datei dient nur dazu, bekannte Gateways und BLE-Geräte nach einem
    Prozess-/Raspberry-Neustart wiederherstellen zu können.

    Wichtig: ``online`` wird beim Laden absichtlich auf ``False`` gesetzt. Erst
    ein echter Refresh/Read darf ein Gerät wieder als online markieren.
    """

    def __init__(self, inventory_path=None, *, autoload=True):
        self.gateways = {}
        self.devices = {}
        self.actuators = {}

        self._lock = threading.RLock()
        self.inventory_path = Path(inventory_path) if inventory_path else _default_inventory_path()
        self.last_inventory_error = None
        self.last_inventory_load_count = 0

        if autoload:
            try:
                self.load_inventory()
            except Exception as exc:
                # Hardware-Persistenz darf den Growstar-Start niemals verhindern.
                self.last_inventory_error = str(exc)
                print("⚠️ Hardware-Inventar konnte nicht geladen werden:", exc)

    # ---------- Gateways ----------

    def add_gateway(self, gateway):
        with self._lock:
            self.gateways[gateway.id] = gateway

    def gateways_list(self):
        with self._lock:
            return list(self.gateways.values())

    def gateway(self, gateway_id):
        with self._lock:
            return self.gateways.get(gateway_id)

    # ---------- Geräte ----------

    def add_device(self, device):
        with self._lock:
            self.devices[device.id] = device

    def devices_list(self):
        with self._lock:
            return list(self.devices.values())

    def device(self, device_id):
        with self._lock:
            return self.devices.get(device_id)

    # ---------- Aktoren ----------

    def add_actuator(self, actuator):
        with self._lock:
            self.actuators[actuator.id] = actuator

    def actuators_list(self):
        with self._lock:
            return list(self.actuators.values())

    # ---------- Allgemein ----------

    def clear(self):
        """Leert nur den Laufzeitbestand.

        Die persistente Recovery-Datei wird absichtlich NICHT gelöscht. Scanner
        dürfen den Manager während einer Suche temporär leeren, ohne dadurch
        bekannte BLE-Pairingdaten dauerhaft zu verlieren.
        """
        with self._lock:
            self.gateways.clear()
            self.devices.clear()
            self.actuators.clear()

    # ---------- Persistenz ----------

    @staticmethod
    def _gateway_from_dict(data):
        gateway = Gateway()
        gateway.id = str(data.get("id") or "")
        gateway.name = str(data.get("name") or "")
        gateway.manufacturer = str(data.get("manufacturer") or "")
        gateway.model = str(data.get("model") or "")
        gateway.online = False
        gateway.properties = deepcopy(data.get("properties") or {})

        gateway.ip = str(data.get("ip") or "")
        gateway.mac = str(data.get("mac") or "")
        gateway.firmware = str(data.get("firmware") or "")
        gateway.bluetooth = bool(data.get("bluetooth", False))
        # Der gespeicherte Wert ist die gewünschte/zuletzt bekannte Einstellung,
        # nicht der aktuelle Onlinezustand. Recovery verifiziert ihn erneut.
        gateway.bluetooth_enabled = bool(data.get("bluetooth_enabled", False))
        gateway.bluetooth_scanning = False
        gateway.bluetooth_scan = {}
        gateway.rssi = data.get("rssi")
        gateway.uptime = None
        gateway.methods = list(data.get("methods") or [])
        gateway.capabilities = deepcopy(data.get("capabilities") or {})
        return gateway

    @staticmethod
    def _device_from_dict(data):
        device = HardwareDevice()
        device.id = str(data.get("id") or "")
        device.name = str(data.get("name") or "")
        device.manufacturer = str(data.get("manufacturer") or "")
        device.model = str(data.get("model") or "")
        device.type = str(data.get("type") or "")
        device.online = False
        device.properties = deepcopy(data.get("properties") or {})
        return device

    def _current_snapshot(self):
        with self._lock:
            gateways = {
                gateway.id: gateway.to_dict()
                for gateway in self.gateways.values()
                if getattr(gateway, "id", None)
            }
            devices = {
                device.id: device.to_dict()
                for device in self.devices.values()
                if getattr(device, "id", None)
            }

        return {
            "version": INVENTORY_VERSION,
            "gateways": gateways,
            "devices": devices,
        }

    def _read_inventory_file(self):
        path = self.inventory_path
        if not path.exists():
            return {"version": INVENTORY_VERSION, "gateways": {}, "devices": {}}

        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        if not isinstance(data, dict):
            raise ValueError("Hardware-Inventar muss ein JSON-Objekt sein")

        gateways = data.get("gateways")
        devices = data.get("devices")

        # Frühere/handgeschriebene Listen ebenfalls tolerant akzeptieren.
        if isinstance(gateways, list):
            gateways = {str(item.get("id")): item for item in gateways if isinstance(item, dict) and item.get("id")}
        if isinstance(devices, list):
            devices = {str(item.get("id")): item for item in devices if isinstance(item, dict) and item.get("id")}

        return {
            "version": int(data.get("version") or INVENTORY_VERSION),
            "gateways": gateways if isinstance(gateways, dict) else {},
            "devices": devices if isinstance(devices, dict) else {},
        }

    @staticmethod
    def _atomic_write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(
            prefix=".hardware-inventory-",
            suffix=".tmp",
            dir=str(path.parent),
            text=True,
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(temp_path, path)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def save_inventory(self, *, merge=True):
        """Speichert Gateways und Geräte atomar.

        ``merge=True`` bewahrt bekannte Einträge, die ein laufender Scanner
        temporär aus dem In-Memory-Manager entfernt hat. Aktuelle Objekte
        überschreiben dabei immer die gespeicherte Version mit gleicher ID.
        """
        current = self._current_snapshot()

        with self._lock:
            if merge:
                try:
                    stored = self._read_inventory_file()
                except Exception:
                    stored = {"version": INVENTORY_VERSION, "gateways": {}, "devices": {}}

                gateways = dict(stored.get("gateways") or {})
                devices = dict(stored.get("devices") or {})
                gateways.update(current["gateways"])
                devices.update(current["devices"])
                payload = {
                    "version": INVENTORY_VERSION,
                    "gateways": gateways,
                    "devices": devices,
                }
            else:
                payload = current

            self._atomic_write(self.inventory_path, payload)
            self.last_inventory_error = None
            return payload

    def load_inventory(self):
        """Mischt persistierte bekannte Hardware in den Laufzeitmanager."""
        data = self._read_inventory_file()
        loaded = 0

        with self._lock:
            for gateway_data in (data.get("gateways") or {}).values():
                if not isinstance(gateway_data, dict):
                    continue
                gateway = self._gateway_from_dict(gateway_data)
                if not gateway.id:
                    continue
                # Bereits live entdeckte Objekte niemals durch Offline-Snapshots
                # überschreiben.
                if gateway.id not in self.gateways:
                    self.gateways[gateway.id] = gateway
                    loaded += 1

            for device_data in (data.get("devices") or {}).values():
                if not isinstance(device_data, dict):
                    continue
                device = self._device_from_dict(device_data)
                if not device.id:
                    continue
                if device.id not in self.devices:
                    self.devices[device.id] = device
                    loaded += 1

            self.last_inventory_load_count = loaded
            self.last_inventory_error = None

        if loaded:
            print(f"♻️ Hardware-Inventar geladen: {loaded} bekannte Einträge")

        return loaded

    def inventory_status(self):
        with self._lock:
            return {
                "path": str(self.inventory_path),
                "exists": self.inventory_path.exists(),
                "gateways": len(self.gateways),
                "devices": len(self.devices),
                "last_load_count": self.last_inventory_load_count,
                "error": self.last_inventory_error,
            }


manager = HardwareManager()
