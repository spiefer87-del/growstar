"""Read-only Aufbereitung physischer Hardware für die zentrale Übersicht."""

import time

from core.constants import SENSOR_TIMEOUT


def fresh_mqtt_vivosun_addresses(sources, *, now=None):
    """Liefert physische VIVOSUN-Adressen, die aktuell über Pico/MQTT kommen."""
    current = time.time() if now is None else float(now)
    addresses = set()
    for source in sources or []:
        source_id = str(source.get("id") or "").lower()
        parts = source_id.split(":")
        if len(parts) != 3 or parts[0] != "vivosun" or source.get("type") != "mqtt":
            continue
        try:
            age = current - float(source.get("last_seen") or 0)
        except (TypeError, ValueError):
            continue
        if 0 <= age <= SENSOR_TIMEOUT:
            addresses.add(parts[1])
    return addresses


def hardware_device_views(devices, *, mqtt_vivosun_addresses=None):
    """Blendet den inaktiven Raspberry-Zwilling eines Pico-Sensors aus."""
    mqtt_vivosun_addresses = set(mqtt_vivosun_addresses or ())
    result = []
    for device in devices or []:
        props = getattr(device, "properties", None) or {}
        if props.get("protocol") == "vivosun_thb1s":
            compact = str(props.get("addr") or "").replace(":", "").lower()
            if compact in mqtt_vivosun_addresses:
                continue
        result.append(device.to_dict())
    return result


def mqtt_device_views(devices):
    """Zeigt Pico-Controller, aber nicht jeden VIVOSUN-Messkanal als Gerät."""
    return [
        dict(device)
        for device in devices or []
        if device.get("protocol") != "vivosun_thb1s"
    ]


__all__ = (
    "fresh_mqtt_vivosun_addresses",
    "hardware_device_views",
    "mqtt_device_views",
)
