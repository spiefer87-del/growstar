import json
import time

import paho.mqtt.client as mqtt

import core.state as state
import core.context as ctx

from core.config import config

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
            temp_raw = float(data["temp"])
        except Exception:
            return

        temp = round(
            temp_raw + float(config.get("TEMP_OFFSET", 0.0)),
            2
        )

        with ctx.state_lock:

            state.last_ds_temp = temp_raw
            state.last_ds_time = now

            state.live_state["temp_raw"] = temp_raw
            state.live_state["temp"] = temp

        return

    # =========================
    # Luftfeuchte
    # =========================

    if msg.topic == TOPIC_DHT and "hum" in data:

        try:
            hum_raw = float(data["hum"])
        except Exception:
            return

        hum = round(
            hum_raw + float(config.get("HUM_OFFSET", 0.0)),
            2
        )

        with ctx.state_lock:

            state.last_hum = hum_raw
            state.last_dht_time = now

            state.live_state["hum_raw"] = hum_raw
            state.live_state["hum"] = hum


def create_client():
    client = mqtt.Client(
        client_id="grow-backend",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )

    client.on_connect = on_connect
    client.on_message = on_message

    return client
