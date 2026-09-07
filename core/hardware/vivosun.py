"""Lokaler BLE-Adapter fuer den VIVOSUN AeroLab VS-THB1S.

Der Sensor verwendet kein BTHome. Er wird direkt ueber den Bluetooth-Adapter
des Raspberry angesprochen. Die oeffentliche Klasse stellt absichtlich nur
Discovery und read-only Messwertabfrage bereit; Konfigurations-, Cloud- oder
Firmware-Schreibpfade gehoeren nicht zu Growstar.
"""

from __future__ import annotations

import asyncio
import math
import re
import struct
import threading
import time

try:
    from bleak import BleakClient, BleakScanner
except ImportError:  # Auf Entwicklungs-/Testsystemen darf Bleak fehlen.
    BleakClient = None
    BleakScanner = None


PROTOCOL = "vivosun_thb1s"
MODEL = "VS-THB1S"
LOCAL_NAME = "ThermoBeacon2"
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
STATUS_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"
COMMAND_UUID = "0000fff5-0000-1000-8000-00805f9b34fb"
READ_STATUS_COMMAND = bytes((0x0D,))

_MAIN_TEMPERATURE_OFFSET = 1
_MAIN_HUMIDITY_OFFSET = 3
_EXTERNAL_TEMPERATURE_OFFSET = 7
_EXTERNAL_HUMIDITY_OFFSET = 9
_MISSING_VALUE = -1
_MIN_PAYLOAD_BYTES = 11
_ADDRESS_RE = re.compile(r"^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$")


class VivosunBleError(RuntimeError):
    """Kontrollierter Fehler des lokalen VIVOSUN-BLE-Pfads."""


def normalize_address(value):
    address = str(value or "").strip().upper()
    if not _ADDRESS_RE.fullmatch(address):
        raise VivosunBleError("Ungueltige Bluetooth-Adresse des VIVOSUN-Sensors")
    return address


def device_id_from_address(value):
    address = normalize_address(value)
    return "vivosun_" + address.replace(":", "").lower()


def _decode_measurement(payload, offset, *, kind):
    raw = struct.unpack_from("<h", payload, offset)[0]
    if raw == _MISSING_VALUE:
        return None

    value = raw / 16.0
    if not math.isfinite(value):
        raise VivosunBleError("VIVOSUN-Sensor lieferte keinen endlichen Messwert")

    if kind == "temperature" and not -40.0 <= value <= 125.0:
        raise VivosunBleError("VIVOSUN-Sensor lieferte eine unplausible Temperatur")
    if kind == "humidity" and not 0.0 <= value <= 100.0:
        raise VivosunBleError("VIVOSUN-Sensor lieferte eine unplausible Luftfeuchtigkeit")

    return round(value, 2)


def decode_status_payload(payload):
    """Dekodiert die aktuelle interne und externe Temperatur/Feuchte."""

    data = bytes(payload or b"")
    if len(data) < _MIN_PAYLOAD_BYTES:
        raise VivosunBleError(
            "VIVOSUN-Statuspaket ist zu kurz "
            f"({len(data)} statt mindestens {_MIN_PAYLOAD_BYTES} Byte)"
        )

    channels = {
        "main": {
            "temperature": _decode_measurement(
                data,
                _MAIN_TEMPERATURE_OFFSET,
                kind="temperature",
            ),
            "humidity": _decode_measurement(
                data,
                _MAIN_HUMIDITY_OFFSET,
                kind="humidity",
            ),
        },
        "external": {
            "temperature": _decode_measurement(
                data,
                _EXTERNAL_TEMPERATURE_OFFSET,
                kind="temperature",
            ),
            "humidity": _decode_measurement(
                data,
                _EXTERNAL_HUMIDITY_OFFSET,
                kind="humidity",
            ),
        },
    }

    for values in channels.values():
        values["available"] = bool(
            values.get("temperature") is not None
            and values.get("humidity") is not None
        )

    if not any(values["available"] for values in channels.values()):
        raise VivosunBleError("VIVOSUN-Statuspaket enthaelt keine nutzbaren Messwerte")

    return {
        "channels": channels,
        "raw_hex": data.hex(),
    }


def _device_name(device):
    return str(
        getattr(device, "name", None)
        or getattr(device, "alias", None)
        or ""
    ).strip()


def _device_rssi(device):
    value = getattr(device, "rssi", None)
    if value is None:
        metadata = getattr(device, "metadata", None) or {}
        value = metadata.get("rssi")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class VivosunTHB1SAdapter:
    """Synchroner, thread-sicherer Mantel um die asynchronen Bleak-Aufrufe."""

    def __init__(
        self,
        *,
        scanner_cls=None,
        client_cls=None,
        async_runner=None,
        now=None,
    ):
        self.scanner_cls = BleakScanner if scanner_cls is None else scanner_cls
        self.client_cls = BleakClient if client_cls is None else client_cls
        self.async_runner = async_runner or asyncio.run
        self.now = now or time.time
        self._lock = threading.Lock()

    def status(self):
        available = bool(self.scanner_cls is not None and self.client_cls is not None)
        return {
            "success": available,
            "available": available,
            "backend": "bleak-bluez",
            "transport": "raspberry-ble",
            "model": MODEL,
            "local_name": LOCAL_NAME,
            "protocol": PROTOCOL,
            "error": None if available else "python3-bleak ist nicht installiert",
        }

    @staticmethod
    def _is_supported(device):
        return _device_name(device).lower() == LOCAL_NAME.lower()

    async def _scan_async(self, timeout):
        devices = await self.scanner_cls.discover(timeout=timeout)
        result = []

        for device in devices or []:
            if not self._is_supported(device):
                continue

            try:
                address = normalize_address(getattr(device, "address", None))
            except VivosunBleError:
                continue

            result.append({
                "address": address,
                "name": _device_name(device) or LOCAL_NAME,
                "rssi": _device_rssi(device),
                "manufacturer": "VIVOSUN",
                "model": MODEL,
                "protocol": PROTOCOL,
            })

        result.sort(key=lambda item: str(item.get("address") or ""))
        return result

    def scan(self, timeout=8):
        if not self.status()["available"]:
            return {
                **self.status(),
                "candidates": [],
                "count": 0,
            }

        try:
            duration = max(2.0, min(float(timeout), 30.0))
        except (TypeError, ValueError):
            duration = 8.0

        if not self._lock.acquire(blocking=False):
            return {
                "success": False,
                "available": True,
                "error": "Eine lokale Bluetooth-Abfrage laeuft bereits.",
                "candidates": [],
                "count": 0,
            }

        try:
            candidates = self.async_runner(self._scan_async(duration))
            return {
                "success": True,
                "available": True,
                "candidates": candidates,
                "count": len(candidates),
                "duration": duration,
            }
        except Exception as exc:
            return {
                "success": False,
                "available": True,
                "error": f"VIVOSUN-Bluetooth-Suche fehlgeschlagen: {exc}",
                "candidates": [],
                "count": 0,
            }
        finally:
            self._lock.release()

    async def _resolve_device(self, address, timeout):
        finder = getattr(self.scanner_cls, "find_device_by_address", None)
        if finder is not None:
            return await finder(address, timeout=timeout)

        devices = await self.scanner_cls.discover(timeout=timeout)
        return next(
            (
                device
                for device in devices or []
                if str(getattr(device, "address", "")).upper() == address
            ),
            None,
        )

    async def _read_async(self, address, connect_timeout, read_timeout):
        device = await self._resolve_device(
            address,
            min(8.0, connect_timeout),
        )
        if device is None:
            raise VivosunBleError(
                "VS-THB1S ist nicht sichtbar. Pair/Sensor-Taste drei Sekunden druecken."
            )
        if not self._is_supported(device):
            raise VivosunBleError(
                "Bluetooth-Adresse gehoert nicht zu einem erkannten VS-THB1S"
            )

        client = self.client_cls(device, timeout=connect_timeout)
        connected = False
        notify_started = False
        future = asyncio.get_running_loop().create_future()

        def on_status(_sender, data):
            if not future.done():
                future.set_result(bytes(data))

        try:
            await client.connect()
            connected = True
            await client.start_notify(STATUS_UUID, on_status)
            notify_started = True
            await client.write_gatt_char(
                COMMAND_UUID,
                READ_STATUS_COMMAND,
            )
            payload = await asyncio.wait_for(future, timeout=read_timeout)
            decoded = decode_status_payload(payload)
            decoded.update({
                "address": address,
                "name": _device_name(device) or LOCAL_NAME,
                "rssi": _device_rssi(device),
                "observed_at": float(self.now()),
            })
            return decoded
        finally:
            if notify_started:
                try:
                    await client.stop_notify(STATUS_UUID)
                except Exception:
                    pass
            if connected:
                try:
                    await client.disconnect()
                except Exception:
                    pass

    def read(self, address, *, connect_timeout=15, read_timeout=3):
        if not self.status()["available"]:
            return {
                "success": False,
                "error": "python3-bleak ist nicht installiert",
            }

        try:
            normalized = normalize_address(address)
            connect_timeout = max(3.0, min(float(connect_timeout), 30.0))
            read_timeout = max(0.5, min(float(read_timeout), 10.0))
        except (TypeError, ValueError, VivosunBleError) as exc:
            return {
                "success": False,
                "error": str(exc),
            }

        if not self._lock.acquire(blocking=False):
            return {
                "success": False,
                "error": "Eine lokale Bluetooth-Abfrage laeuft bereits.",
            }

        try:
            result = self.async_runner(
                self._read_async(
                    normalized,
                    connect_timeout,
                    read_timeout,
                )
            )
            result["success"] = True
            return result
        except Exception as exc:
            return {
                "success": False,
                "error": f"VIVOSUN-Messwertabfrage fehlgeschlagen: {exc}",
            }
        finally:
            self._lock.release()


vivosun_adapter = VivosunTHB1SAdapter()


__all__ = (
    "COMMAND_UUID",
    "LOCAL_NAME",
    "MODEL",
    "PROTOCOL",
    "READ_STATUS_COMMAND",
    "SERVICE_UUID",
    "STATUS_UUID",
    "VivosunBleError",
    "VivosunTHB1SAdapter",
    "decode_status_payload",
    "device_id_from_address",
    "normalize_address",
    "vivosun_adapter",
)
