#!/usr/bin/env python3

import importlib.util
import json
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parent
SERVICE = ROOT / "services" / "mqtt.py"


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


# Minimal fake dependencies so this test needs neither paho nor the full app.
paho = types.ModuleType("paho")
paho_mqtt = types.ModuleType("paho.mqtt")
paho_client = types.ModuleType("paho.mqtt.client")

class CallbackAPIVersion:
    VERSION2 = 2

class DummyClient:
    def __init__(self, *args, **kwargs):
        self.subscriptions = None
        self.on_connect = None
        self.on_message = None
    def subscribe(self, subscriptions):
        self.subscriptions = subscriptions

paho_client.CallbackAPIVersion = CallbackAPIVersion
paho_client.Client = DummyClient
paho_mqtt.client = paho_client
paho.mqtt = paho_mqtt
sys.modules["paho"] = paho
sys.modules["paho.mqtt"] = paho_mqtt
sys.modules["paho.mqtt.client"] = paho_client

core = types.ModuleType("core")
context = types.ModuleType("core.context")
context.MQTT_LAST_MSG = 0
sensor_sources = types.ModuleType("core.sensor_sources")
updates = []

def update_sensor_source(source_id, **kwargs):
    updates.append((source_id, kwargs))
    return {"id": source_id, **kwargs}

sensor_sources.update_sensor_source = update_sensor_source
core.context = context
core.sensor_sources = sensor_sources
sys.modules["core"] = core
sys.modules["core.context"] = context
sys.modules["core.sensor_sources"] = sensor_sources

spec = importlib.util.spec_from_file_location("phase4mqtt_service", SERVICE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Msg:
    def __init__(self, topic, data):
        self.topic = topic
        self.payload = json.dumps(data).encode("utf-8")


def main():
    text = SERVICE.read_text(encoding="utf-8")

    require("growstar/sensors/+/state" in text,
            "Generisches Wildcard-Topic vorhanden")
    require('TOPIC_DS = "sensor/ds18b20"' in text and
            'TOPIC_DHT = "sensor/dht22"' in text,
            "Legacy MQTT-Topics bleiben erhalten")
    require("tent_1" not in text and "tent_2" not in text,
            "MQTT-Empfänger enthält keine Stations-Sonderlogik")

    client = DummyClient()
    module.on_connect(client, None, None, 0, None)
    topics = {topic for topic, qos in client.subscriptions}
    require(module.TOPIC_SENSOR_STATE in topics,
            "Growstar subscribed auf beliebig viele Pico-Sensoren")
    require(module.TOPIC_DS in topics and module.TOPIC_DHT in topics,
            "Legacy Sensoren werden weiter subscribed")

    updates.clear()
    module.on_message(None, None, Msg("sensor/ds18b20", {"temp": 21.5}))
    require(updates[-1][0] == "mqtt:ds18b20" and
            updates[-1][1]["temperature"] == 21.5,
            "Legacy DS18B20 bleibt kompatibel")

    module.on_message(None, None, Msg("sensor/dht22", {"hum": 57.2}))
    require(updates[-1][0] == "mqtt:dht22" and
            updates[-1][1]["humidity"] == 57.2,
            "Legacy DHT22 bleibt kompatibel")

    module.on_message(None, None, Msg(
        "growstar/sensors/pico_zelt2/state",
        {
            "device_id": "pico_zelt2",
            "name": "Pico Zelt 2",
            "temperature": 24.3,
            "humidity": 52.1,
            "rssi": -61,
            "uptime": 1234,
        },
    ))
    source_id, data = updates[-1]
    require(source_id == "mqtt:pico_zelt2",
            "Pico erhält stabile dynamische source_id")
    require(data["temperature"] == 24.3 and data["humidity"] == 52.1,
            "Ein Pico kann Temperatur und Feuchte gemeinsam liefern")
    require(data["label"] == "Pico Zelt 2" and data["rssi"] == -61.0,
            "Pico-Metadaten werden übernommen")

    module.on_message(None, None, Msg(
        "growstar/sensors/pico_zelt3/state",
        {"temp": 23.0, "hum": 49.0},
    ))
    require(updates[-1][0] == "mqtt:pico_zelt3",
            "Weitere Picos benötigen keinen neuen Backend-Code")

    before = len(updates)
    module.on_message(None, None, Msg(
        "growstar/sensors/bad/id/state",
        {"temperature": 99},
    ))
    require(len(updates) == before,
            "Ungültige verschachtelte Geräte-ID wird ignoriert")

    module.on_message(None, None, Msg(
        "growstar/sensors/pico_zelt4/state",
        {"device_id": "falsche_id", "temperature": 20.0},
    ))
    require(updates[-1][0] == "mqtt:pico_zelt4",
            "Topic-ID bleibt kanonisch bei Payload-Mismatch")

    require(context.MQTT_LAST_MSG > 0,
            "Controller-MQTT-Heartbeat wird weiter aktualisiert")

    print("✅ Multi-Pico MQTT Backend vollständig")


if __name__ == "__main__":
    main()
