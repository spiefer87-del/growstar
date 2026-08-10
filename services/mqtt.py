import json
import re
import time

import paho.mqtt.client as mqtt

import core.context as ctx

from core.mqtt_sensor_devices import (
    update_mqtt_sensor_state,
    update_mqtt_sensor_status,
)
from core.sensor_sources import update_sensor_source


MQTT_BROKER = "localhost"
MQTT_PORT = 1883

# Bestehende Topics bleiben vollständig kompatibel.
TOPIC_DS = "sensor/ds18b20"
TOPIC_DHT = "sensor/dht22"

# Portable Sensorcontroller. Die Geräte-ID beschreibt Hardware, kein Zelt.
TOPIC_SENSOR_STATE = "growstar/sensors/+/state"
TOPIC_SENSOR_STATUS = "growstar/sensors/+/status"
_TOPIC_PREFIX = "growstar/sensors/"

_DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _float_or_none(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _device_id_from_topic(topic, suffix):
    topic = str(topic or "")
    suffix = "/" + str(suffix).strip("/")

    if not topic.startswith(_TOPIC_PREFIX) or not topic.endswith(suffix):
        return None

    device_id = topic[len(_TOPIC_PREFIX):-len(suffix)]
    if not device_id or "/" in device_id:
        return None
    if not _DEVICE_ID_RE.fullmatch(device_id):
        return None

    return device_id


def _decode_payload(msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))
    except Exception as exc:
        print("❌ MQTT JSON Fehler:", exc)
        return None

    if not isinstance(data, dict):
        print("❌ MQTT Payload muss ein JSON-Objekt sein")
        return None

    return data


def _handle_legacy_message(topic, data):
    """Bestehende Legacy-Topics unverändert weiter unterstützen."""
    if topic == TOPIC_DS and "temp" in data:
        temperature = _float_or_none(data.get("temp"))
        if temperature is None:
            print("❌ MQTT Temperatur ungültig")
            return True

        update_sensor_source(
            "mqtt:ds18b20",
            label="Alter Temperatursensor",
            source_type="mqtt",
            temperature=temperature,
            raw=data,
        )
        return True

    if topic == TOPIC_DHT and "hum" in data:
        humidity = _float_or_none(data.get("hum"))
        if humidity is None:
            print("❌ MQTT Feuchte ungültig")
            return True

        update_sensor_source(
            "mqtt:dht22",
            label="Alter Feuchtesensor",
            source_type="mqtt",
            humidity=humidity,
            raw=data,
        )
        return True

    return topic in (TOPIC_DS, TOPIC_DHT)


def _handle_sensor_status(topic, data):
    device_id = _device_id_from_topic(topic, "status")
    if device_id is None:
        return False

    payload_device_id = data.get("device_id")
    if payload_device_id not in (None, "", device_id):
        print(
            f"⚠️ MQTT status device_id passt nicht zum Topic: "
            f"{payload_device_id!r} != {device_id!r}; Topic-ID wird verwendet"
        )

    update_mqtt_sensor_status(
        device_id,
        data,
        topic=topic,
    )
    return True


def _handle_generic_sensor_message(topic, data):
    """Verarbeitet growstar/sensors/<device_id>/state.

    ``device_id`` bezeichnet ausschließlich den physischen Sensorcontroller.
    Eine Zuordnung zu Zelt/Station findet hier absichtlich NICHT statt.
    """
    device_id = _device_id_from_topic(topic, "state")
    if device_id is None:
        return False

    payload_device_id = data.get("device_id")
    if payload_device_id not in (None, "", device_id):
        print(
            f"⚠️ MQTT device_id passt nicht zum Topic: "
            f"{payload_device_id!r} != {device_id!r}; Topic-ID wird verwendet"
        )

    temperature = _float_or_none(data.get("temperature", data.get("temp")))
    humidity = _float_or_none(data.get("humidity", data.get("hum")))
    battery = _float_or_none(data.get("battery"))
    rssi = _float_or_none(data.get("rssi"))

    label = (
        str(data.get("name") or data.get("label") or "").strip()
        or f"MQTT Sensor {device_id}"
    )

    update_mqtt_sensor_state(
        device_id,
        data,
        topic=topic,
    )

    update_sensor_source(
        f"mqtt:{device_id}",
        label=label,
        source_type="mqtt",
        temperature=temperature,
        humidity=humidity,
        battery=battery,
        rssi=rssi,
        raw=data,
    )

    return True


def on_connect(client, userdata, flags, reason_code, properties):
    try:
        connected = int(reason_code) == 0
    except (TypeError, ValueError):
        connected = reason_code == 0

    if not connected:
        print("❌ MQTT Verbindung fehlgeschlagen:", reason_code)
        return

    print("✅ MQTT verbunden")

    client.subscribe([
        (TOPIC_DS, 0),
        (TOPIC_DHT, 0),
        (TOPIC_SENSOR_STATE, 0),
        (TOPIC_SENSOR_STATUS, 0),
    ])

    print(
        "📡 MQTT Sensor-Topics aktiv: "
        f"{TOPIC_DS}, {TOPIC_DHT}, {TOPIC_SENSOR_STATE}, {TOPIC_SENSOR_STATUS}"
    )


def on_message(client, userdata, msg):
    ctx.MQTT_LAST_MSG = time.time()

    data = _decode_payload(msg)
    if data is None:
        return

    topic = str(msg.topic or "")

    try:
        if _handle_legacy_message(topic, data):
            return
        if _handle_sensor_status(topic, data):
            return
        if _handle_generic_sensor_message(topic, data):
            return
    except Exception as exc:
        print(f"❌ MQTT Sensor Fehler ({topic}):", exc)


def create_client():
    client = mqtt.Client(
        client_id="grow-backend",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    client.on_connect = on_connect
    client.on_message = on_message
    return client
