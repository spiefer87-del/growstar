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


def fresh_mqtt_vivosun_details(sources, *, now=None):
    """Fasst die frischen MQTT-Kanäle je physischem VIVOSUN zusammen."""
    current = time.time() if now is None else float(now)
    result = {}
    for source in sources or []:
        source_id = str(source.get("id") or "").lower()
        parts = source_id.split(":")
        if len(parts) != 3 or parts[0] != "vivosun" or source.get("type") != "mqtt":
            continue
        try:
            last_seen = float(source.get("last_seen") or 0)
        except (TypeError, ValueError):
            continue
        if not 0 <= current - last_seen <= SENSOR_TIMEOUT:
            continue
        raw = source.get("raw") if isinstance(source.get("raw"), dict) else {}
        address = parts[1]
        detail = result.setdefault(address, {"channels": {}, "last_seen": 0})
        channel = parts[2]
        detail["channels"][channel] = {
            "temperature": source.get("temperature"),
            "humidity": source.get("humidity"),
            "available": source.get("temperature") is not None and source.get("humidity") is not None,
            "last_seen": last_seen,
        }
        detail["last_seen"] = max(detail["last_seen"], last_seen)
        detail["rssi"] = source.get("rssi")
        detail["bridge_id"] = raw.get("bridge_id") or detail.get("bridge_id")
        detail["bridge_name"] = raw.get("bridge_name") or detail.get("bridge_name")
        detail["ble_address"] = raw.get("ble_address") or detail.get("ble_address")
    return result


def hardware_device_views(devices, *, mqtt_vivosun_details=None, mqtt_vivosun_addresses=None):
    """Zeigt jedes physische BLE-Gerät einmal mit seinem aktiven Transport."""
    mqtt_vivosun_details = dict(mqtt_vivosun_details or {})
    mqtt_vivosun_addresses = set(mqtt_vivosun_addresses or ())
    result = []
    for device in devices or []:
        props = getattr(device, "properties", None) or {}
        if props.get("protocol") == "vivosun_thb1s":
            compact = str(props.get("addr") or "").replace(":", "").lower()
            detail = mqtt_vivosun_details.get(compact)
            if detail is None and compact in mqtt_vivosun_addresses:
                detail = {"channels": {}, "last_seen": props.get("last_seen")}
            if detail is not None:
                view = device.to_dict()
                view["online"] = True
                view_props = dict(props)
                view_props.update({
                    "transport": "pico_wifi_ble_bridge",
                    "connection_label": "%s (MQTT)" % (
                        detail.get("bridge_name") or detail.get("bridge_id") or "Pico"
                    ),
                    "last_seen": detail.get("last_seen"),
                    "rssi": detail.get("rssi", props.get("rssi")),
                    "channels": detail.get("channels") or props.get("channels") or {},
                })
                view["properties"] = view_props
                result.append(view)
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
    "fresh_mqtt_vivosun_details",
    "hardware_device_views",
    "mqtt_device_views",
)
