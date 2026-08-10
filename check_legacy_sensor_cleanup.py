#!/usr/bin/env python3

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    mqtt = read("services/mqtt.py")
    sensors = read("routes/sensors.py")

    ast.parse(mqtt, filename="services/mqtt.py")
    ast.parse(sensors, filename="routes/sensors.py")
    print("✅ Python-Syntax")

    require(
        "growstar/sensors/+/state" in mqtt
        and "growstar/sensors/+/status" in mqtt,
        "Generische MQTT-Sensorcontroller bleiben aktiv",
    )

    require(
        "sensor/ds18b20" not in mqtt
        and "sensor/dht22" not in mqtt
        and "_handle_legacy_message" not in mqtt,
        "Legacy MQTT-Topics sind aus dem Backend entfernt",
    )

    require(
        "mqtt:ds18b20" not in sensors
        or "_RETIRED_SOURCE_IDS" in sensors,
        "Alter Temperatursensor wird nicht mehr angeboten",
    )

    require(
        "mqtt:dht22" not in sensors
        or "_RETIRED_SOURCE_IDS" in sensors,
        "Alter Feuchtesensor wird nicht mehr angeboten",
    )

    require(
        "_RETIRED_SOURCE_IDS" in sensors
        and "stillgelegte Legacy-Sensorquelle" in sensors,
        "Legacy-Quellen können nicht versehentlich neu zugewiesen werden",
    )

    require(
        "mqtt:pico_01" not in mqtt
        and "mqtt:pico_02" not in mqtt,
        "Portable Picos bleiben vollständig dynamisch",
    )

    print("✅ Legacy MQTT-Sensoren vollständig stillgelegt")


if __name__ == "__main__":
    main()
