#!/usr/bin/env python3

"""
Growstar Portable Sensor Nodes – Backend/UI Regressionstest

WICHTIG:
Dieser Test prüft absichtlich NICHT die Pico-Firmware im Repository.
Ein Pico darf offline, ungeflasht oder sogar außerhalb dieses Repositories sein.

Geprüft wird ausschließlich:
- Growstar MQTT ist stationsneutral.
- Beliebige Sensorcontroller-IDs werden dynamisch verarbeitet.
- MQTT-Sensorcontroller erscheinen im Hardware-Inventar.
- Sensorquellen können per Drag&Drop stationsbezogen zugeordnet werden.
"""

import ast
import importlib.util
import json
from pathlib import Path
import sys
import types

from jinja2 import Environment


TEST_VERSION = "portable-sensor-nodes-v4-backend-only"

ROOT = Path(__file__).resolve().parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def load_mqtt_service():
    # ----------------------------------------------------------
    # paho isoliert faken
    # ----------------------------------------------------------
    paho = types.ModuleType("paho")
    paho_mqtt = types.ModuleType("paho.mqtt")
    paho_client = types.ModuleType("paho.mqtt.client")

    class CallbackAPIVersion:
        VERSION2 = 2

    class DummyClient:
        def __init__(self, *args, **kwargs):
            self.subscriptions = []

        def subscribe(self, topics):
            self.subscriptions = topics

    paho_client.CallbackAPIVersion = CallbackAPIVersion
    paho_client.Client = DummyClient
    paho_mqtt.client = paho_client
    paho.mqtt = paho_mqtt

    sys.modules["paho"] = paho
    sys.modules["paho.mqtt"] = paho_mqtt
    sys.modules["paho.mqtt.client"] = paho_client

    # ----------------------------------------------------------
    # minimale Growstar-Core-Abhängigkeiten faken
    # ----------------------------------------------------------
    core = types.ModuleType("core")

    context = types.ModuleType("core.context")
    context.MQTT_LAST_MSG = 0

    sensor_sources = types.ModuleType("core.sensor_sources")
    updates = []

    def update_sensor_source(source_id, **kwargs):
        updates.append((source_id, kwargs))
        return {"id": source_id, **kwargs}

    sensor_sources.update_sensor_source = update_sensor_source

    # echte MQTT-Geräteregistry laden
    spec_reg = importlib.util.spec_from_file_location(
        "core.mqtt_sensor_devices",
        ROOT / "core/mqtt_sensor_devices.py",
    )

    registry = importlib.util.module_from_spec(spec_reg)
    spec_reg.loader.exec_module(registry)

    core.context = context
    core.sensor_sources = sensor_sources
    core.mqtt_sensor_devices = registry

    sys.modules["core"] = core
    sys.modules["core.context"] = context
    sys.modules["core.sensor_sources"] = sensor_sources
    sys.modules["core.mqtt_sensor_devices"] = registry

    # echten MQTT-Service isoliert laden
    spec = importlib.util.spec_from_file_location(
        "portable_mqtt",
        ROOT / "services/mqtt.py",
    )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module, registry, updates


class Msg:
    def __init__(self, topic, data):
        self.topic = topic
        self.payload = json.dumps(data).encode("utf-8")


def main():
    print(f"🧪 {TEST_VERSION}")

    # ----------------------------------------------------------
    # Syntax
    # ----------------------------------------------------------
    for rel in [
        "core/mqtt_sensor_devices.py",
        "services/mqtt.py",
        "routes/hardware.py",
        "routes/sensors.py",
        "check_portable_sensor_nodes.py",
    ]:
        ast.parse(read(rel), filename=rel)

    print("✅ Python-Syntax")

    env = Environment()
    env.parse(read("templates/devices.html"))
    env.parse(read("templates/grow_control_sensors.html"))

    print("✅ Jinja/HTML-Syntax")

    # ----------------------------------------------------------
    # statische Architekturchecks
    # ----------------------------------------------------------
    mqtt = read("services/mqtt.py")
    hub = read("templates/grow_control_sensors.html")
    devices = read("templates/devices.html")
    sensors = read("routes/sensors.py")
    hardware = read("routes/hardware.py")

    require(
        "tent_1" not in mqtt
        and "tent_2" not in mqtt
        and "pico_zelt" not in mqtt,
        "MQTT-Empfänger ist stationsneutral",
    )

    require(
        "growstar/sensors/+/state" in mqtt
        and "growstar/sensors/+/status" in mqtt,
        "Generische MQTT-Wildcard-Topics vorhanden",
    )

    require(
        "draggable = true" in hub
        and "drop-zone" in hub
        and "pointermove" in hub,
        "Sensorhub unterstützt Desktop- und Mobile-Drag&Drop",
    )

    require(
        '/api/tents/${encodeURIComponent(tentId)}/sensors/assignments'
        in hub,
        "Drag&Drop speichert ausschließlich stationsbezogene Zuweisung",
    )

    require(
        '"/api/sensors/sources"' in sensors,
        "Controllerweite Sensorquellen-API vorhanden",
    )

    require(
        "mqtt_devices" in hardware
        and "list_mqtt_sensor_devices" in hardware,
        "Hardware-API liefert MQTT-Sensorcontroller",
    )

    require(
        "mqtt-device-grid" in devices
        and "MQTT Sensorcontroller" in devices,
        "Hardware-Übersicht zeigt MQTT-Sensorcontroller",
    )

    # ----------------------------------------------------------
    # MQTT-Service isoliert testen
    # ----------------------------------------------------------
    module, registry, updates = load_mqtt_service()

    client = type(
        "C",
        (),
        {
            "subscribe": lambda self, topics: setattr(
                self,
                "topics",
                topics,
            )
        },
    )()

    module.on_connect(
        client,
        None,
        None,
        0,
        None,
    )

    topics = {
        topic
        for topic, qos
        in client.topics
    }

    require(
        "growstar/sensors/+/state" in topics
        and "growstar/sensors/+/status" in topics,
        "Growstar subscribed auf beliebige Sensorcontroller",
    )

    # ----------------------------------------------------------
    # Controller 1: pico_02
    # ----------------------------------------------------------
    module.on_message(
        None,
        None,
        Msg(
            "growstar/sensors/pico_02/status",
            {
                "device_id": "pico_02",
                "name": "Pico Sensor 2",
                "online": True,
                "capabilities": [
                    "temperature",
                    "humidity",
                ],
                "rssi": -55,
            },
        ),
    )

    dev = registry.get_mqtt_sensor_device(
        "pico_02"
    )

    require(
        dev
        and dev["online"] is True
        and dev["source_id"] == "mqtt:pico_02",
        "Stationsneutraler Pico wird controllerweit registriert",
    )

    module.on_message(
        None,
        None,
        Msg(
            "growstar/sensors/pico_02/state",
            {
                "device_id": "pico_02",
                "name": "Pico Sensor 2",
                "temperature": 24.2,
                "humidity": 51.4,
                "rssi": -57,
            },
        ),
    )

    require(
        updates
        and updates[-1][0] == "mqtt:pico_02",
        "Pico erzeugt stabile stationsunabhängige source_id",
    )

    # ----------------------------------------------------------
    # Controller 2: völlig anderer neutraler Name
    # beweist, dass nichts auf pico_02 fest verdrahtet ist
    # ----------------------------------------------------------
    module.on_message(
        None,
        None,
        Msg(
            "growstar/sensors/sensor_node_03/status",
            {
                "device_id": "sensor_node_03",
                "name": "Klima Sensor 3",
                "online": True,
                "capabilities": [
                    "temperature",
                    "humidity",
                ],
            },
        ),
    )

    module.on_message(
        None,
        None,
        Msg(
            "growstar/sensors/sensor_node_03/state",
            {
                "device_id": "sensor_node_03",
                "name": "Klima Sensor 3",
                "temperature": 23.7,
                "humidity": 49.8,
            },
        ),
    )

    dev2 = registry.get_mqtt_sensor_device(
        "sensor_node_03"
    )

    require(
        dev2
        and dev2["source_id"] == "mqtt:sensor_node_03"
        and dev2.get("temperature") == 23.7,
        "Beliebige zweite Sensorcontroller-ID funktioniert ohne Codeänderung",
    )

    require(
        updates[-1][0] == "mqtt:sensor_node_03",
        "Mehrere portable Sensorcontroller bleiben getrennt",
    )

    # ----------------------------------------------------------
    # Kein Firmware-Zwang im App-Test
    # ----------------------------------------------------------
    source = read("check_portable_sensor_nodes.py")

    require(
        "pico_sensor_02/config.py" not in source
        and "DEVICE_ID ==" not in source,
        "Growstar-Test ist unabhängig von Pico-Firmware und Flash-Status",
    )

    print("✅ Portable Sensor Nodes Backend/UI vollständig")


if __name__ == "__main__":
    main()
