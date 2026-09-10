"""VIVOSUN AeroLab VS-THB1S BLE client for the Growstar Pico bridge.

Newer VS-THB1S revisions publish their measurements in a manufacturer
advertisement and reject active GATT connections. Older ``ThermoBeacon2``
revisions still use notifications and status command 0x0D. This adapter
supports both variants and always prefers the passive, battery-friendly path.

This module intentionally uses MicroPython's built-in low-level ``bluetooth``
API.  No cloud, VIVOSUN account or additional Pico package is required.
"""

import time

try:
    import bluetooth
except ImportError:
    bluetooth = None


PROTOCOL = "vivosun_thb1s"
MODEL = "VIVOSUN AeroLab VS-THB1S"
LOCAL_NAME = "ThermoBeacon2"

_SERVICE_UUID_TEXT = "0000fff0-0000-1000-8000-00805f9b34fb"
_STATUS_UUID_TEXT = "0000fff3-0000-1000-8000-00805f9b34fb"
_COMMAND_UUID_TEXT = "0000fff5-0000-1000-8000-00805f9b34fb"
_READ_STATUS_COMMAND = b"\x0d"

_ADVERTISEMENT_MANUFACTURER_IDS = (0x0019, 0x8019)
_ADVERTISEMENT_PAYLOAD_BYTES = 20

_IRQ_SCAN_RESULT = 5
_IRQ_SCAN_DONE = 6
_IRQ_PERIPHERAL_CONNECT = 7
_IRQ_PERIPHERAL_DISCONNECT = 8
_IRQ_GATTC_SERVICE_RESULT = 9
_IRQ_GATTC_SERVICE_DONE = 10
_IRQ_GATTC_CHARACTERISTIC_RESULT = 11
_IRQ_GATTC_CHARACTERISTIC_DONE = 12
_IRQ_GATTC_DESCRIPTOR_RESULT = 13
_IRQ_GATTC_DESCRIPTOR_DONE = 14
_IRQ_GATTC_WRITE_DONE = 17
_IRQ_GATTC_NOTIFY = 18

_CCCD_UUID_NUMBER = 0x2902
_MIN_PAYLOAD_BYTES = 11
_MISSING_VALUE = -1


class VivosunBridgeError(Exception):
    pass


def normalize_address(value):
    address = str(value or "").strip().upper().replace("-", ":")
    parts = address.split(":")
    if len(parts) != 6:
        raise VivosunBridgeError("Ungueltige VIVOSUN Bluetooth-Adresse")

    normalized = []
    for part in parts:
        if len(part) != 2:
            raise VivosunBridgeError("Ungueltige VIVOSUN Bluetooth-Adresse")
        try:
            number = int(part, 16)
        except ValueError:
            raise VivosunBridgeError("Ungueltige VIVOSUN Bluetooth-Adresse")
        normalized.append("%02X" % number)

    return ":".join(normalized)


def device_id_from_address(address, channel):
    channel = str(channel or "").strip().lower()
    if channel not in ("main", "external"):
        raise VivosunBridgeError("Unbekannter VIVOSUN Sensorkanal")
    return "vivosun_%s_%s" % (
        normalize_address(address).replace(":", "").lower(),
        channel,
    )


def _address_bytes(address):
    normalized = normalize_address(address)
    return bytes(int(part, 16) for part in normalized.split(":"))


def _decode_name(adv_data):
    data = bytes(adv_data or b"")
    offset = 0

    while offset + 1 < len(data):
        length = data[offset]
        if length == 0:
            break

        end = offset + length + 1
        if end > len(data):
            break

        field_type = data[offset + 1]
        if field_type in (0x08, 0x09):
            try:
                return data[offset + 2:end].decode("utf-8").strip()
            except Exception:
                return ""

        offset = end

    return ""


def _iter_advertisement_fields(adv_data):
    data = bytes(adv_data or b"")
    offset = 0

    while offset + 1 < len(data):
        length = data[offset]
        if length == 0:
            break

        end = offset + length + 1
        if end > len(data):
            break

        yield data[offset + 1], data[offset + 2:end]
        offset = end


def _decode_advertisement(adv_data):
    """Return a validated passive measurement or ``None``."""
    has_service = False
    manufacturer_payloads = {}

    for field_type, value in _iter_advertisement_fields(adv_data):
        if field_type in (0x02, 0x03):
            for offset in range(0, len(value) - 1, 2):
                if value[offset] == 0xF0 and value[offset + 1] == 0xFF:
                    has_service = True
        elif field_type == 0xFF and len(value) >= 2:
            manufacturer_id = value[0] | (value[1] << 8)
            manufacturer_payloads[manufacturer_id] = bytes(value[2:])

    if not has_service:
        return None

    for manufacturer_id in _ADVERTISEMENT_MANUFACTURER_IDS:
        payload = manufacturer_payloads.get(manufacturer_id)
        if payload is None or len(payload) != _ADVERTISEMENT_PAYLOAD_BYTES:
            continue
        try:
            decoded = decode_advertisement_payload(payload)
        except VivosunBridgeError:
            continue
        decoded["manufacturer_id"] = manufacturer_id
        return decoded

    return None


def _signed_little_endian_16(data, offset):
    value = data[offset] | (data[offset + 1] << 8)
    if value & 0x8000:
        value -= 0x10000
    return value


def _decode_measurement(data, offset, kind):
    raw = _signed_little_endian_16(data, offset)
    if raw == _MISSING_VALUE:
        return None

    value = raw / 16.0
    if kind == "temperature" and not -40.0 <= value <= 125.0:
        raise VivosunBridgeError("Unplausible VIVOSUN Temperatur")
    if kind == "humidity" and not 0.0 <= value <= 100.0:
        raise VivosunBridgeError("Unplausible VIVOSUN Luftfeuchtigkeit")
    return round(value, 2)


def decode_status_payload(payload):
    data = bytes(payload or b"")
    if len(data) < _MIN_PAYLOAD_BYTES:
        raise VivosunBridgeError(
            "VIVOSUN Statuspaket zu kurz (%s Byte)" % len(data)
        )

    channels = {
        "main": {
            "temperature": _decode_measurement(data, 1, "temperature"),
            "humidity": _decode_measurement(data, 3, "humidity"),
        },
        "external": {
            "temperature": _decode_measurement(data, 7, "temperature"),
            "humidity": _decode_measurement(data, 9, "humidity"),
        },
    }

    usable = False
    for values in channels.values():
        values["available"] = (
            values["temperature"] is not None
            and values["humidity"] is not None
        )
        usable = usable or values["available"]

    if not usable:
        raise VivosunBridgeError("VIVOSUN Paket enthaelt keine Messwerte")

    return channels


def decode_advertisement_payload(payload):
    """Decode the open 20-byte advertisement of newer VS-THB1S units."""
    data = bytes(payload or b"")
    if len(data) != _ADVERTISEMENT_PAYLOAD_BYTES:
        raise VivosunBridgeError(
            "VIVOSUN Advertisement hat %s statt %s Byte"
            % (len(data), _ADVERTISEMENT_PAYLOAD_BYTES)
        )

    channels = {
        "main": {
            "temperature": _decode_measurement(data, 8, "temperature"),
            "humidity": _decode_measurement(data, 10, "humidity"),
        },
        "external": {
            "temperature": _decode_measurement(data, 12, "temperature"),
            "humidity": _decode_measurement(data, 14, "humidity"),
        },
    }

    for values in channels.values():
        values["available"] = (
            values["temperature"] is not None
            and values["humidity"] is not None
        )

    if not channels["main"]["available"]:
        raise VivosunBridgeError(
            "VIVOSUN Advertisement enthaelt keine Hauptmesswerte"
        )

    battery_mv = data[6] | (data[7] << 8)
    if not 1500 <= battery_mv <= 5000:
        raise VivosunBridgeError(
            "VIVOSUN Advertisement enthaelt unplausible Batteriespannung"
        )

    uptime_seconds = (
        data[16]
        | (data[17] << 8)
        | (data[18] << 16)
        | (data[19] << 24)
    )
    return {
        "channels": channels,
        "battery_voltage": round(battery_mv / 1000.0, 3),
        "uptime_seconds": uptime_seconds,
        "raw_hex": "".join("%02x" % value for value in data),
        "measurement_source": "advertisement",
    }


class VivosunTHB1SBridge:
    """Blocking single-connection GATT client for use in the Pico main loop."""

    def __init__(self):
        if bluetooth is None:
            raise VivosunBridgeError(
                "MicroPython-Firmware besitzt kein bluetooth-Modul"
            )

        self._service_uuid = bluetooth.UUID(_SERVICE_UUID_TEXT)
        self._status_uuid = bluetooth.UUID(_STATUS_UUID_TEXT)
        self._command_uuid = bluetooth.UUID(_COMMAND_UUID_TEXT)
        self._cccd_uuid = bluetooth.UUID(_CCCD_UUID_NUMBER)
        self._ble = bluetooth.BLE()
        self._ble.active(True)
        try:
            self._ble.config(rxbuf=512)
        except Exception:
            pass
        self._ble.irq(self._irq)
        self._reset_operation()

    def _reset_operation(self):
        self._target_address = None
        self._scan_done = False
        self._scan_match = None
        self._conn_handle = None
        self._disconnected = False
        self._service = None
        self._service_done = False
        self._service_status = None
        self._characteristics = []
        self._characteristics_done = False
        self._characteristics_status = None
        self._descriptors = []
        self._descriptors_done = False
        self._descriptors_status = None
        self._write_done = None
        self._notification = None
        self._status_value_handle = None

    @staticmethod
    def _uuid(value):
        return bluetooth.UUID(value)

    def _irq(self, event, data):
        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, _adv_type, rssi, adv_data = data
            address = bytes(addr)
            if self._target_address is None or address != self._target_address:
                return

            name = _decode_name(adv_data)
            current = self._scan_match or {}
            current["addr_type"] = int(addr_type)
            current["addr"] = address
            current["rssi"] = int(rssi)
            if name:
                current["local_name"] = name
            fragments = list(current.get("adv_fragments") or ())
            fragment = bytes(adv_data or b"")
            if fragment and fragment not in fragments:
                fragments.append(fragment)
                fragments = fragments[-8:]
            current["adv_fragments"] = fragments
            passive = _decode_advertisement(b"".join(fragments))
            if passive is not None:
                current["passive"] = passive
            self._scan_match = current

        elif event == _IRQ_SCAN_DONE:
            self._scan_done = True

        elif event == _IRQ_PERIPHERAL_CONNECT:
            conn_handle, _addr_type, addr = data
            if self._target_address is None or bytes(addr) == self._target_address:
                self._conn_handle = int(conn_handle)
                self._disconnected = False

        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            conn_handle, _addr_type, _addr = data
            if self._conn_handle is None or int(conn_handle) == self._conn_handle:
                self._conn_handle = None
                self._disconnected = True

        elif event == _IRQ_GATTC_SERVICE_RESULT:
            conn_handle, start_handle, end_handle, uuid = data
            if int(conn_handle) == self._conn_handle:
                if self._uuid(uuid) == self._service_uuid:
                    self._service = (int(start_handle), int(end_handle))

        elif event == _IRQ_GATTC_SERVICE_DONE:
            conn_handle, status = data
            if int(conn_handle) == self._conn_handle:
                self._service_status = int(status)
                self._service_done = True

        elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
            conn_handle, def_handle, value_handle, properties, uuid = data
            if int(conn_handle) == self._conn_handle:
                self._characteristics.append((
                    int(def_handle),
                    int(value_handle),
                    int(properties),
                    self._uuid(uuid),
                ))

        elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
            conn_handle, status = data
            if int(conn_handle) == self._conn_handle:
                self._characteristics_status = int(status)
                self._characteristics_done = True

        elif event == _IRQ_GATTC_DESCRIPTOR_RESULT:
            conn_handle, descriptor_handle, uuid = data
            if int(conn_handle) == self._conn_handle:
                self._descriptors.append((
                    int(descriptor_handle),
                    self._uuid(uuid),
                ))

        elif event == _IRQ_GATTC_DESCRIPTOR_DONE:
            conn_handle, status = data
            if int(conn_handle) == self._conn_handle:
                self._descriptors_status = int(status)
                self._descriptors_done = True

        elif event == _IRQ_GATTC_WRITE_DONE:
            conn_handle, value_handle, status = data
            if int(conn_handle) == self._conn_handle:
                self._write_done = (int(value_handle), int(status))

        elif event == _IRQ_GATTC_NOTIFY:
            conn_handle, value_handle, notify_data = data
            if (
                int(conn_handle) == self._conn_handle
                and int(value_handle) == self._status_value_handle
            ):
                self._notification = bytes(notify_data)

    def _wait(self, predicate, timeout_sec, error_message, connected=False):
        deadline = time.ticks_add(
            time.ticks_ms(),
            int(float(timeout_sec) * 1000),
        )

        while not predicate():
            if connected and self._disconnected:
                raise VivosunBridgeError("VIVOSUN Verbindung wurde getrennt")
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                raise VivosunBridgeError(error_message)
            time.sleep_ms(20)

    def _scan(self, address, timeout_sec):
        self._target_address = _address_bytes(address)
        self._scan_done = False
        self._scan_match = None

        duration_ms = max(1000, int(float(timeout_sec) * 1000))
        self._ble.gap_scan(duration_ms, 30000, 15000, True)

        try:
            self._wait(
                lambda: self._scan_done or (
                    self._scan_match is not None
                    and (
                        self._scan_match.get("local_name") == LOCAL_NAME
                        or self._scan_match.get("passive") is not None
                    )
                ),
                timeout_sec + 1,
                "VIVOSUN BLE-Suche ohne Ergebnis",
            )
        finally:
            try:
                self._ble.gap_scan(None)
            except Exception:
                pass
            if not self._scan_done:
                try:
                    self._wait(
                        lambda: self._scan_done,
                        1,
                        "VIVOSUN BLE-Suche konnte nicht beendet werden",
                    )
                except VivosunBridgeError:
                    pass

        if self._scan_match is None:
            raise VivosunBridgeError(
                "VS-THB1S nicht sichtbar; Pair/Sensor-Taste druecken"
            )

        observed_name = self._scan_match.get("local_name")
        if observed_name and observed_name != LOCAL_NAME:
            raise VivosunBridgeError(
                "Bluetooth-Adresse meldet sich nicht als ThermoBeacon2"
            )

        return self._scan_match

    def _discover_handles(self, timeout_sec):
        self._service_done = False
        self._service_status = None
        self._service = None
        self._ble.gattc_discover_services(
            self._conn_handle,
            self._service_uuid,
        )
        self._wait(
            lambda: self._service_done,
            timeout_sec,
            "VIVOSUN Service-Suche abgelaufen",
            connected=True,
        )
        if self._service_status != 0 or self._service is None:
            raise VivosunBridgeError("VIVOSUN GATT-Service fehlt")

        self._characteristics = []
        self._characteristics_done = False
        self._characteristics_status = None
        self._ble.gattc_discover_characteristics(
            self._conn_handle,
            self._service[0],
            self._service[1],
        )
        self._wait(
            lambda: self._characteristics_done,
            timeout_sec,
            "VIVOSUN Characteristic-Suche abgelaufen",
            connected=True,
        )
        if self._characteristics_status != 0:
            raise VivosunBridgeError("VIVOSUN Characteristics nicht lesbar")

        status_handle = None
        command_handle = None
        status_descriptor_end = self._service[1]
        ordered = sorted(self._characteristics, key=lambda item: item[0])

        for index, item in enumerate(ordered):
            def_handle, value_handle, _properties, uuid = item
            if uuid == self._status_uuid:
                status_handle = value_handle
                if index + 1 < len(ordered):
                    status_descriptor_end = ordered[index + 1][0] - 1
            elif uuid == self._command_uuid:
                command_handle = value_handle

        if status_handle is None or command_handle is None:
            raise VivosunBridgeError("VIVOSUN Status-/Kommando-Kanal fehlt")

        descriptor_start = status_handle + 1
        if descriptor_start > status_descriptor_end:
            raise VivosunBridgeError("VIVOSUN Notify-Descriptor fehlt")

        self._descriptors = []
        self._descriptors_done = False
        self._descriptors_status = None
        self._ble.gattc_discover_descriptors(
            self._conn_handle,
            descriptor_start,
            status_descriptor_end,
        )
        self._wait(
            lambda: self._descriptors_done,
            timeout_sec,
            "VIVOSUN Descriptor-Suche abgelaufen",
            connected=True,
        )
        if self._descriptors_status != 0:
            raise VivosunBridgeError("VIVOSUN Descriptor-Suche fehlgeschlagen")

        cccd_handle = None
        for descriptor_handle, uuid in self._descriptors:
            if uuid == self._cccd_uuid:
                cccd_handle = descriptor_handle
                break

        if cccd_handle is None:
            raise VivosunBridgeError("VIVOSUN Notify-Descriptor fehlt")

        return status_handle, command_handle, cccd_handle

    def _write_with_response(self, value_handle, value, timeout_sec):
        self._write_done = None
        self._ble.gattc_write(
            self._conn_handle,
            value_handle,
            value,
            1,
        )
        self._wait(
            lambda: self._write_done is not None,
            timeout_sec,
            "VIVOSUN Schreibbestaetigung abgelaufen",
            connected=True,
        )
        if self._write_done != (value_handle, 0):
            raise VivosunBridgeError("VIVOSUN GATT-Schreibvorgang fehlgeschlagen")

    def read(self, address, scan_timeout_sec=6, connect_timeout_sec=12,
             read_timeout_sec=4):
        """Read passively when possible, otherwise use the legacy GATT path."""
        address = normalize_address(address)
        self._reset_operation()
        scan = self._scan(address, scan_timeout_sec)

        passive = scan.get("passive")
        if passive is not None:
            result = dict(passive)
            result.update({
                "address": address,
                "rssi": scan.get("rssi"),
                "local_name": scan.get("local_name") or LOCAL_NAME,
            })
            return result

        try:
            self._ble.gap_connect(
                scan["addr_type"],
                scan["addr"],
                max(2000, int(float(connect_timeout_sec) * 1000)),
            )
            self._wait(
                lambda: self._conn_handle is not None,
                connect_timeout_sec + 1,
                "VIVOSUN BLE-Verbindung abgelaufen",
            )

            status_handle, command_handle, cccd_handle = self._discover_handles(
                read_timeout_sec
            )
            self._status_value_handle = status_handle
            self._write_with_response(
                cccd_handle,
                b"\x01\x00",
                read_timeout_sec,
            )

            self._notification = None
            # The command characteristic is write-without-response on the
            # VS-THB1S; the following notification is the confirmation.
            self._ble.gattc_write(
                self._conn_handle,
                command_handle,
                _READ_STATUS_COMMAND,
                0,
            )
            self._wait(
                lambda: self._notification is not None,
                read_timeout_sec,
                "VIVOSUN Statusantwort abgelaufen",
                connected=True,
            )

            return {
                "address": address,
                "rssi": scan.get("rssi"),
                "local_name": scan.get("local_name") or LOCAL_NAME,
                "channels": decode_status_payload(self._notification),
            }
        finally:
            if self._conn_handle is not None:
                try:
                    self._ble.gap_disconnect(self._conn_handle)
                except Exception:
                    pass
            else:
                try:
                    self._ble.gap_connect(None)
                except Exception:
                    pass
