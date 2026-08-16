#!/usr/bin/env python3
"""Phase 4O.1 – MQTT-Hardware-UI Regression Fix.

Hardware-/netzwerkfrei. Prueft, dass Phase 4O die bereits vorhandene
Pico/MQTT-Sensorcontroller-Ansicht nicht entfernt und die neue Aktoransicht
parallel bestehen bleibt.
"""
from pathlib import Path

try:
    from jinja2 import Environment
except ModuleNotFoundError:
    Environment = None

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    devices = (ROOT / "templates" / "devices.html").read_text(encoding="utf-8")

    if Environment is not None:
        Environment().parse(devices)
        print("✅ Jinja/HTML-Syntax Phase 4O.1")

    require(
        'id="mqtt-device-grid"' in devices
        and "MQTT Sensorcontroller" in devices,
        "Hardware-Uebersicht zeigt weiterhin MQTT-Sensorcontroller",
    )
    require(
        "data.mqtt_devices || []" in devices
        and "function renderMqttDevices(devices)" in devices,
        "MQTT-Sensorcontroller werden weiterhin aus /api/hardware gerendert",
    )
    require(
        'id="mqtt-device-count"' in devices,
        "Hardware-Status zaehlt MQTT-Sensorcontroller weiterhin separat",
    )
    require(
        "function formatUptime(seconds)" in devices,
        "Uptime-Formatter ist wieder vorhanden",
    )
    require(
        "data.assigned_actuators" in devices
        and "Keine Aktor-Zuordnungen" in devices
        and "Gateway" in devices,
        "Neue Phase-4O-Aktoransicht bleibt erhalten",
    )
    require(
        "RSSI ${device.rssi" in devices
        and "RSSI ${gateway.rssi" in devices,
        "MQTT-Sensor- und Gateway-Metadaten koexistieren in derselben Hardware-Seite",
    )

    print("✅ Phase 4O.1 MQTT-Hardware-UI Regression Fix vollstaendig")


if __name__ == "__main__":
    main()
