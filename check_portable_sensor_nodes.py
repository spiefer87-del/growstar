#!/usr/bin/env python3

import ast
import importlib.util
import json
from pathlib import Path
import sys
import types

from jinja2 import Environment

ROOT = Path(__file__).resolve().parent

TEST_VERSION = "portable-sensor-nodes-v3"


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def read_python_constants(rel):
    source = read(rel)
    tree = ast.parse(source, filename=rel)
    values = {}

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1:
            continue

        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue

        if isinstance(node.value, ast.Constant):
            values[target.id] = node.value.value

    return values


def load_mqtt_service():
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

    core = types.ModuleType("core")
    context = types.ModuleType("core.context")
    context.MQTT_LAST_MSG = 0

    sensor_sources = types.ModuleType("core.sensor_sources")
    updates = []

    def update_sensor_source(source_id, **kwargs):
        updates.append((source_id, kwargs))

    sensor_sources.update_sensor_source = update_sensor_source

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
        self.payload = json.dumps(data).encode()


def main():
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

    mqtt = read("services/mqtt.py")
    pico_values = read_python_constants("pico_sensor_02/config.py")
    hub = read("templates/grow_control_sensors.html")
    devices = read("templates/devices.html")
    sensors = read("routes/sensors.py")
    hardware = read("routes/hardware.py")

    require(
        "tent_1" not in mqtt and "tent_2" not in mqtt,
        "MQTT-Empfänger ist stationsneutral",
    )

    device_id = str(pico_values.get("DEVICE_ID", ""))
    device_name = str(pico_values.get("DEVICE_NAME", ""))

    import re

    require(
        bool(device_id)
        and bool(device_name)
        and re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", device_id) is not None
        and "zelt" not in device_id.lower()
        and "tent" not in device_id.lower()
        and "zelt" not in device_name.lower()
        and "tent" not in device_name.lower(),
        "Pico-ID ist gültig und nicht an ein Zelt gekoppelt",
    )

    require(
        "draggable = true" in hub
        and "drop-zone" in hub
        and "pointermove" in hub,
        "Sensorhub unterstützt Desktop- und Mobile-Drag&Drop",
    )

    require(
        '/api/tents/${encodeURIComponent(tentId)}/sensors/assignments' in hub,
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
        "Hardware-Übersicht zeigt Pico/MQTT-Sensorcontroller",
    )

    module, registry, updates = load_mqtt_service()

    client = type(
        "C",
        (),
        {"subscribe": lambda self, topics: setattr(self, "topics", topics)},
    )()

    module.on_connect(client, None, None, 0, None)

    topics = {topic for topic, qos in client.topics}

    require(
        "growstar/sensors/+/state" in topics
        and "growstar/sensors/+/status" in topics,
        "Growstar empfängt State und retained Status beliebiger Sensorcontroller",
    )

    module.on_message(
        None,
        None,
        Msg(
            "growstar/sensors/pico_02/status",
            {
                "device_id": "pico_02",
                "name": "Pico Sensor 2",
                "online": True,
                "capabilities": ["temperature", "humidity"],
                "rssi": -55,
            },
        ),
    )

    dev = registry.get_mqtt_sensor_device("pico_02")

    require(
        dev
        and dev["online"] is True
        and dev["source_id"] == "mqtt:pico_02",
        "Retained Status registriert Pico controllerweit",
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
                "capabilities": ["temperature", "humidity"],
            },
        ),
    )

    require(
        updates and updates[-1][0] == "mqtt:pico_02",
        "Pico erzeugt stabile stationsunabhängige source_id",
    )

    dev = registry.get_mqtt_sensor_device("pico_02")

    require(
        dev and dev.get("temperature") == 24.2,
        "Hardware-Inventar erhält Pico-Telemetrie",
    )

    print("✅ Portable Sensor Nodes vollständig")


if __name__ == "__main__":
    main()
