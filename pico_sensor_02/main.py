import time
import machine
import network
import dht
import onewire
import ds18x20

try:
    import ujson as json
except ImportError:
    import json

from umqttsimple import MQTTClient
from vivosun_ble import (
    MODEL as VIVOSUN_MODEL,
    PROTOCOL as VIVOSUN_PROTOCOL,
    VivosunBridgeError,
    VivosunTHB1SBridge,
    device_id_from_address as vivosun_device_id,
    normalize_address as normalize_vivosun_address,
)
from config import (
    SSID,
    PASSWORD,
    MQTT_BROKER,
    MQTT_PORT,
    MQTT_USER,
    MQTT_PASSWORD,
    DEVICE_ID,
    DEVICE_NAME,
    DEVICE_MODEL,
    FIRMWARE_VERSION,
    CLIENT_ID,
    TOPIC_STATE,
    TOPIC_STATUS,
    DHT22_PIN,
    DS18B20_PIN,
    SAFE_MODE_PIN,
    PUBLISH_INTERVAL_SEC,
    WIFI_CONNECT_TIMEOUT_SEC,
    WIFI_RETRY_SEC,
    MQTT_RETRY_SEC,
    DS_RESCAN_INTERVAL_SEC,
)

import config as local_config


def _optional_seconds(name, default, minimum):
    try:
        value = int(getattr(local_config, name, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


# Bestehende config.py-Dateien bleiben nach dem Firmware-Update gueltig.
# Ohne explizite Zieladresse ist die Bruecke sicher inaktiv.
VIVOSUN_BRIDGE_TARGETS = getattr(local_config, "VIVOSUN_BRIDGE_TARGETS", ())
VIVOSUN_BRIDGE_INTERVAL_SEC = _optional_seconds(
    "VIVOSUN_BRIDGE_INTERVAL_SEC", 10, 5
)
VIVOSUN_BLE_SCAN_TIMEOUT_SEC = _optional_seconds(
    "VIVOSUN_BLE_SCAN_TIMEOUT_SEC", 6, 2
)
VIVOSUN_BLE_CONNECT_TIMEOUT_SEC = _optional_seconds(
    "VIVOSUN_BLE_CONNECT_TIMEOUT_SEC", 12, 3
)
VIVOSUN_BLE_READ_TIMEOUT_SEC = _optional_seconds(
    "VIVOSUN_BLE_READ_TIMEOUT_SEC", 4, 2
)


# ============================================================
# Helfer
# ============================================================

def _valid_device_id(value):
    if not value or len(value) > 64:
        return False

    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"

    if value[0] not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
        return False

    for char in value:
        if char not in allowed:
            return False

    return True


def _json_bytes(data):
    return json.dumps(data).encode()


def _uptime_seconds():
    return max(0, time.ticks_diff(time.ticks_ms(), START_TICKS) // 1000)


def _wifi_rssi():
    try:
        return int(wlan.status("rssi"))
    except Exception:
        return None


def _sleep_seconds(seconds):
    # Kleine Sleep-Hilfe, damit die Hauptlogik gut lesbar bleibt.
    time.sleep(seconds)


# ============================================================
# Sicherer Start
# ============================================================

time.sleep(3)
print("Growstar Pico startet:", DEVICE_NAME, "(" + DEVICE_ID + ")")

if not _valid_device_id(DEVICE_ID):
    raise ValueError("Ungueltige DEVICE_ID: " + str(DEVICE_ID))

safe_pin = machine.Pin(SAFE_MODE_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
if safe_pin.value() == 0:
    print("SAFE MODE aktiv - keine WLAN/MQTT Verbindung")
    while True:
        time.sleep(1)


# ============================================================
# Sensoren
# ============================================================

dht_sensor = dht.DHT22(machine.Pin(DHT22_PIN))

ow = onewire.OneWire(machine.Pin(DS18B20_PIN))
ds_sensor = ds18x20.DS18X20(ow)
ds_roms = []
last_ds_scan_ticks = 0


def scan_ds18b20(force=False):
    global ds_roms, last_ds_scan_ticks

    now = time.ticks_ms()

    if not force and ds_roms:
        return ds_roms

    if not force and time.ticks_diff(now, last_ds_scan_ticks) < DS_RESCAN_INTERVAL_SEC * 1000:
        return ds_roms

    last_ds_scan_ticks = now

    try:
        ds_roms = ds_sensor.scan()
    except Exception as exc:
        ds_roms = []
        print("DS18B20 Scan-Fehler:", exc)
        return ds_roms

    if ds_roms:
        print("DS18B20 gefunden:", len(ds_roms))
    else:
        print("Kein DS18B20 gefunden")

    return ds_roms


def read_dht22():
    try:
        dht_sensor.measure()
        temperature = dht_sensor.temperature()
        humidity = dht_sensor.humidity()

        if temperature is not None:
            temperature = float(temperature)
        if humidity is not None:
            humidity = float(humidity)

        return temperature, humidity

    except Exception as exc:
        print("DHT22 Fehler:", exc)
        return None, None


def read_ds18b20():
    if not scan_ds18b20():
        return None

    try:
        ds_sensor.convert_temp()
        time.sleep_ms(750)
        value = ds_sensor.read_temp(ds_roms[0])

        if value is None:
            return None

        return float(value)

    except Exception as exc:
        print("DS18B20 Fehler:", exc)
        # Bei naechstem Zyklus neu suchen koennen.
        ds_roms[:] = []
        return None


# ============================================================
# VIVOSUN BLE-zu-WLAN-Bruecke
# ============================================================

def _configured_vivosun_targets():
    result = []
    seen = set()

    for raw in VIVOSUN_BRIDGE_TARGETS or ():
        if not isinstance(raw, dict):
            print("VIVOSUN Ziel ignoriert (kein Dictionary):", raw)
            continue

        try:
            address = normalize_vivosun_address(raw.get("address"))
        except Exception as exc:
            print("VIVOSUN Ziel ignoriert:", exc)
            continue

        if address == "AA:BB:CC:DD:EE:FF":
            print("VIVOSUN Beispieladresse ignoriert:", address)
            continue

        if address in seen:
            print("VIVOSUN Ziel doppelt ignoriert:", address)
            continue

        seen.add(address)
        result.append({
            "address": address,
            "name": str(raw.get("name") or "VIVOSUN VS-THB1S").strip(),
        })

    return result


vivosun_targets = _configured_vivosun_targets()
vivosun_bridge = None
vivosun_bridge_error = None
vivosun_next_reads = {}

if vivosun_targets:
    try:
        vivosun_bridge = VivosunTHB1SBridge()
        print("VIVOSUN Bruecke bereit:", len(vivosun_targets), "Ziel(e)")
    except Exception as exc:
        vivosun_bridge_error = str(exc)
        print("VIVOSUN Bruecke nicht verfuegbar:", exc)


def _vivosun_label(target, channel):
    suffix = "Interner Sensor" if channel == "main" else "Externer Fuehler"
    return "%s - %s" % (target["name"], suffix)


def _vivosun_topic(device_id, suffix):
    return ("growstar/sensors/%s/%s" % (device_id, suffix)).encode()


def _vivosun_status_payload(target, channel, online, reason=None, rssi=None):
    device_id = vivosun_device_id(target["address"], channel)
    payload = {
        "device_id": device_id,
        "name": _vivosun_label(target, channel),
        "model": VIVOSUN_MODEL + " via Pico W",
        "firmware": FIRMWARE_VERSION,
        "device_class": "sensor",
        "transport": "pico_wifi_ble_bridge",
        "protocol": VIVOSUN_PROTOCOL,
        "capabilities": ["temperature", "humidity"],
        "publish_interval": VIVOSUN_BRIDGE_INTERVAL_SEC,
        "online": bool(online),
        "bridge_id": DEVICE_ID,
        "bridge_name": DEVICE_NAME,
        "ble_address": target["address"],
        "channel": channel,
        "uptime": _uptime_seconds(),
    }
    if rssi is not None:
        payload["rssi"] = rssi
    if reason:
        payload["reason"] = str(reason)
    return _json_bytes(payload)


def _publish_vivosun_offline(target, reason):
    # Beide moeglichen Kanaele als offline markieren. Falls kein externer
    # Fuehler vorhanden ist, bleibt dessen Status lediglich Diagnose-Metadatum.
    for channel in ("main", "external"):
        device_id = vivosun_device_id(target["address"], channel)
        mqtt_client.publish(
            _vivosun_topic(device_id, "status"),
            _vivosun_status_payload(
                target,
                channel,
                False,
                reason=reason,
            ),
            retain=True,
            qos=0,
        )


def publish_due_vivosun_bridge_state():
    """Read at most one due target so normal Pico telemetry stays responsive."""
    if mqtt_client is None or not vivosun_targets:
        return False

    now = time.ticks_ms()
    target = None

    for candidate in vivosun_targets:
        deadline = vivosun_next_reads.get(candidate["address"], 0)
        if time.ticks_diff(now, deadline) >= 0:
            target = candidate
            break

    if target is None:
        return False

    vivosun_next_reads[target["address"]] = time.ticks_add(
        now,
        int(VIVOSUN_BRIDGE_INTERVAL_SEC * 1000),
    )

    if vivosun_bridge is None:
        _publish_vivosun_offline(
            target,
            vivosun_bridge_error or "BLE-Bruecke nicht verfuegbar",
        )
        return False

    try:
        result = vivosun_bridge.read(
            target["address"],
            scan_timeout_sec=VIVOSUN_BLE_SCAN_TIMEOUT_SEC,
            connect_timeout_sec=VIVOSUN_BLE_CONNECT_TIMEOUT_SEC,
            read_timeout_sec=VIVOSUN_BLE_READ_TIMEOUT_SEC,
        )
    except VivosunBridgeError as exc:
        print("VIVOSUN BLE-Fehler", target["address"], ":", exc)
        _publish_vivosun_offline(target, exc)
        return False
    except Exception as exc:
        print("VIVOSUN unerwarteter BLE-Fehler", target["address"], ":", exc)
        _publish_vivosun_offline(target, exc)
        return False

    published = 0
    for channel in ("main", "external"):
        values = (result.get("channels") or {}).get(channel) or {}
        if not values.get("available"):
            continue

        device_id = vivosun_device_id(target["address"], channel)
        payload = {
            "device_id": device_id,
            "name": _vivosun_label(target, channel),
            "model": VIVOSUN_MODEL + " via Pico W",
            "firmware": FIRMWARE_VERSION,
            "device_class": "sensor",
            "transport": "pico_wifi_ble_bridge",
            "protocol": VIVOSUN_PROTOCOL,
            "capabilities": ["temperature", "humidity"],
            "publish_interval": VIVOSUN_BRIDGE_INTERVAL_SEC,
            "uptime": _uptime_seconds(),
            "temperature": values["temperature"],
            "humidity": values["humidity"],
            "rssi": result.get("rssi"),
            "measurement_source": result.get("measurement_source") or "gatt",
            "battery_voltage": result.get("battery_voltage"),
            "sensor_uptime": result.get("uptime_seconds"),
            "advertisement_manufacturer_id": result.get("manufacturer_id"),
            "bridge_id": DEVICE_ID,
            "bridge_name": DEVICE_NAME,
            "ble_address": target["address"],
            "channel": channel,
        }

        mqtt_client.publish(
            _vivosun_topic(device_id, "state"),
            _json_bytes(payload),
            retain=False,
            qos=0,
        )
        mqtt_client.publish(
            _vivosun_topic(device_id, "status"),
            _vivosun_status_payload(
                target,
                channel,
                True,
                rssi=result.get("rssi"),
            ),
            retain=True,
            qos=0,
        )
        published += 1

        print(
            "VIVOSUN MQTT State:",
            device_id,
            "temp=", payload["temperature"],
            "hum=", payload["humidity"],
            "ble_rssi=", payload.get("rssi"),
        )

    return published > 0


# ============================================================
# WLAN
# ============================================================

wlan = network.WLAN(network.STA_IF)
wlan.active(True)


def connect_wifi():
    if wlan.isconnected():
        return True

    print("WLAN verbinden...")

    try:
        wlan.disconnect()
    except Exception:
        pass

    try:
        wlan.connect(SSID, PASSWORD)
    except Exception as exc:
        print("WLAN connect Fehler:", exc)
        return False

    deadline = time.ticks_add(
        time.ticks_ms(),
        int(WIFI_CONNECT_TIMEOUT_SEC * 1000),
    )

    while not wlan.isconnected():
        if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
            print("WLAN FEHLGESCHLAGEN")
            return False
        time.sleep_ms(250)

    print("WLAN OK:", wlan.ifconfig())
    return True


# ============================================================
# MQTT
# ============================================================

mqtt_client = None


def _status_payload(online, reason=None):
    payload = {
        "device_id": DEVICE_ID,
        "name": DEVICE_NAME,
        "model": DEVICE_MODEL,
        "firmware": FIRMWARE_VERSION,
        "device_class": "sensor_controller",
        "transport": "mqtt",
        "capabilities": ["temperature", "humidity"],
        "publish_interval": PUBLISH_INTERVAL_SEC,
        "online": bool(online),
        "uptime": _uptime_seconds(),
        "bridge_protocols": [VIVOSUN_PROTOCOL],
        "bridge_targets": len(vivosun_targets),
        "bridge_available": bool(vivosun_bridge is not None),
    }

    if vivosun_bridge_error:
        payload["bridge_error"] = vivosun_bridge_error

    rssi = _wifi_rssi()
    if rssi is not None:
        payload["rssi"] = rssi

    if reason:
        payload["reason"] = reason

    return _json_bytes(payload)


def disconnect_mqtt():
    global mqtt_client

    client = mqtt_client
    mqtt_client = None

    if client is None:
        return

    try:
        client.publish(
            TOPIC_STATUS,
            _status_payload(False, "disconnect"),
            retain=True,
        )
    except Exception:
        pass

    try:
        client.disconnect()
    except Exception:
        pass


def connect_mqtt():
    global mqtt_client

    if not wlan.isconnected():
        return False

    client = None

    try:
        client = MQTTClient(
            CLIENT_ID,
            MQTT_BROKER,
            port=MQTT_PORT,
            user=MQTT_USER,
            password=MQTT_PASSWORD,
            keepalive=60,
        )

        # Broker markiert den Pico automatisch offline, wenn die Verbindung
        # unerwartet abbricht. Growstar wertet /status heute noch nicht aus,
        # das Topic ist aber fuer Diagnose/Watchdog bereits vorbereitet.
        client.set_last_will(
            TOPIC_STATUS,
            _status_payload(False, "lost_connection"),
            retain=True,
            qos=0,
        )

        client.connect(clean_session=True)

        client.publish(
            TOPIC_STATUS,
            _status_payload(True),
            retain=True,
        )

        mqtt_client = client
        print("MQTT verbunden:", MQTT_BROKER)
        return True

    except Exception as exc:
        print("MQTT Fehler:", exc)

        if client is not None:
            try:
                client.disconnect()
            except Exception:
                pass

        mqtt_client = None
        return False


def publish_sensor_state():
    if mqtt_client is None:
        return False

    # Beide Sensoren unabhaengig lesen. Ein DHT-Fehler darf den DS18B20 nicht
    # blockieren und umgekehrt.
    dht_temp, humidity = read_dht22()
    temperature = read_ds18b20()

    # Historische Semantik beibehalten:
    # - Growstar-Temperatur = DS18B20
    # - Growstar-Luftfeuchte = DHT22
    # DHT-Temperatur wird nur als Diagnose-Rohwert mitgesendet.
    payload = {
        "device_id": DEVICE_ID,
        "name": DEVICE_NAME,
        "model": DEVICE_MODEL,
        "firmware": FIRMWARE_VERSION,
        "device_class": "sensor_controller",
        "transport": "mqtt",
        "capabilities": ["temperature", "humidity"],
        "publish_interval": PUBLISH_INTERVAL_SEC,
        "uptime": _uptime_seconds(),
        "temperature_sensor": "ds18b20",
        "humidity_sensor": "dht22",
    }

    if temperature is not None:
        payload["temperature"] = round(temperature, 2)

    if humidity is not None:
        payload["humidity"] = round(humidity, 2)

    if dht_temp is not None:
        payload["dht_temperature"] = round(dht_temp, 2)

    rssi = _wifi_rssi()
    if rssi is not None:
        payload["rssi"] = rssi

    # Wenn beide fuer Growstar relevanten Messwerte fehlen, kein State-Paket
    # senden. Dadurch wird ein defekter Pico/Sensor nicht kuenstlich "frisch".
    if temperature is None and humidity is None:
        print("Keine gueltigen Sensorwerte - kein MQTT State gesendet")
        return False

    message = _json_bytes(payload)

    # State bewusst NICHT retained senden. Ein alter Retain-Wert duerfte nach
    # einem Growstar-Neustart sonst als frisch empfangener Sensorwert wirken.
    mqtt_client.publish(
        TOPIC_STATE,
        message,
        retain=False,
        qos=0,
    )

    print(
        "MQTT State:",
        "temp=", payload.get("temperature"),
        "hum=", payload.get("humidity"),
        "rssi=", payload.get("rssi"),
    )

    return True


# ============================================================
# Hauptprogramm
# ============================================================

START_TICKS = time.ticks_ms()
scan_ds18b20(force=True)

next_wifi_retry = 0
next_mqtt_retry = 0

while True:
    now = time.ticks_ms()

    try:
        if not wlan.isconnected():
            if mqtt_client is not None:
                disconnect_mqtt()

            if time.ticks_diff(now, next_wifi_retry) >= 0:
                if connect_wifi():
                    next_mqtt_retry = 0
                next_wifi_retry = time.ticks_add(
                    time.ticks_ms(),
                    int(WIFI_RETRY_SEC * 1000),
                )

            _sleep_seconds(1)
            continue

        if mqtt_client is None:
            if time.ticks_diff(now, next_mqtt_retry) >= 0:
                connect_mqtt()
                next_mqtt_retry = time.ticks_add(
                    time.ticks_ms(),
                    int(MQTT_RETRY_SEC * 1000),
                )

            if mqtt_client is None:
                _sleep_seconds(1)
                continue

        try:
            publish_sensor_state()
            publish_due_vivosun_bridge_state()

        except Exception as exc:
            print("MQTT Publish-Fehler:", exc)
            disconnect_mqtt()
            next_mqtt_retry = time.ticks_add(
                time.ticks_ms(),
                int(MQTT_RETRY_SEC * 1000),
            )

    except Exception as exc:
        # Der Hauptloop darf bei einem einzelnen Sensor-/Netzwerkfehler nicht
        # sterben. Der naechste Zyklus versucht die Verbindung erneut.
        print("Loop-Fehler:", exc)
        disconnect_mqtt()

    _sleep_seconds(PUBLISH_INTERVAL_SEC)
