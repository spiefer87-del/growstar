import json
import time

import paho.mqtt.client as mqtt

import core.state as state
import core.context as ctx

from core.config import config

from services.sensor import (
        update_temperature,
        update_humidity,
    )

MQTT_BROKER = "localhost"
MQTT_PORT = 1883

TOPIC_DS = "sensor/ds18b20"
TOPIC_DHT = "sensor/dht22"


def on_connect(client, userdata, flags, reason_code, properties):

    if reason_code == 0:
        print("✅ MQTT verbunden")
        client.subscribe([
            (TOPIC_DS, 0),
            (TOPIC_DHT, 0)
        ])


def on_message(client, userdata, msg):

    ctx.MQTT_LAST_MSG = time.time()

    try:
        data = json.loads(msg.payload.decode())
    except Exception as e:
        print("❌ MQTT JSON Fehler:", e)
        return

    now = time.time()

    # =========================
    # Temperatur
    # =========================

    if msg.topic == TOPIC_DS and "temp" in data:

        try:
            update_temperature(float(data["temp"]))
        except Exception:
            return
    
        return

    # =========================
    # Luftfeuchte
    # =========================

    if msg.topic == TOPIC_DHT and "hum" in data:

        try:
            update_humidity(float(data["hum"]))
        except Exception:
            return
    
        return


def create_client():
    client = mqtt.Client(
        client_id="grow-backend",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )

    client.on_connect = on_connect
    client.on_message = on_message

    return client
