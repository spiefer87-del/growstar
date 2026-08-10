"""Controller-weites Inventar für MQTT-Sensorcontroller.

Die Geräte gehören ausdrücklich NICHT zu einer Grow-Station. Eine Station
referenziert sie ausschließlich über SENSOR_ASSIGNMENTS, z. B. mqtt:pico_02.

Der MQTT-Status ist getrennt von der Sensor-Frische: ein Pico kann per MQTT
online sein, obwohl ein einzelner angeschlossener Sensor gerade keine Werte
liefert. Die Regelung verwendet für Frische weiterhin core.sensor_sources.
"""

from copy import deepcopy
import threading
import time


_lock = threading.RLock()
_devices = {}


def _float_or_none(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _capabilities(data, existing=None):
    caps = set(existing or [])

    raw = data.get("capabilities") if isinstance(data, dict) else None
    if isinstance(raw, (list, tuple)):
        for item in raw:
            item = str(item or "").strip().lower()
            if item in ("temperature", "humidity"):
                caps.add(item)

    if isinstance(data, dict):
        if data.get("temperature") is not None or data.get("temp") is not None:
            caps.add("temperature")
        if data.get("humidity") is not None or data.get("hum") is not None:
            caps.add("humidity")

    return sorted(caps)


def _base_device(device_id, current=None):
    current = dict(current or {})
    current["id"] = str(device_id)
    current["source_id"] = "mqtt:" + str(device_id)
    current["transport"] = "mqtt"
    current["device_class"] = current.get("device_class") or "sensor_controller"
    current.setdefault("online", False)
    return current


def update_mqtt_sensor_state(device_id, data, *, topic=None, now=None):
    """Aktualisiert Telemetrie und markiert den Sensorcontroller online."""
    if not device_id or not isinstance(data, dict):
        return None

    timestamp = time.time() if now is None else float(now)

    with _lock:
        current = _base_device(device_id, _devices.get(device_id))
        current["name"] = str(
            data.get("name") or data.get("label") or current.get("name") or f"Pico {device_id}"
        )
        current["model"] = str(data.get("model") or current.get("model") or "MQTT Sensorcontroller")
        current["online"] = True
        current["last_seen"] = timestamp
        current["last_state"] = timestamp
        current["temperature"] = _float_or_none(
            data.get("temperature", data.get("temp"))
        )
        current["humidity"] = _float_or_none(
            data.get("humidity", data.get("hum"))
        )
        current["rssi"] = _float_or_none(data.get("rssi"))
        current["uptime"] = _int_or_none(data.get("uptime"))
        current["publish_interval"] = _float_or_none(data.get("publish_interval"))
        current["firmware"] = data.get("firmware") or current.get("firmware")
        current["capabilities"] = _capabilities(data, current.get("capabilities"))
        current["topic_state"] = topic or current.get("topic_state")
        current["raw_state"] = deepcopy(data)

        _devices[str(device_id)] = current
        return deepcopy(current)


def update_mqtt_sensor_status(device_id, data, *, topic=None, now=None):
    """Übernimmt das retained Online/Offline-Statuspaket eines Controllers."""
    if not device_id or not isinstance(data, dict):
        return None

    timestamp = time.time() if now is None else float(now)

    with _lock:
        current = _base_device(device_id, _devices.get(device_id))
        current["name"] = str(
            data.get("name") or data.get("label") or current.get("name") or f"Pico {device_id}"
        )
        current["model"] = str(data.get("model") or current.get("model") or "MQTT Sensorcontroller")
        if "online" in data:
            current["online"] = bool(data.get("online"))
        current["last_status"] = timestamp
        current["rssi"] = _float_or_none(data.get("rssi")) if data.get("rssi") is not None else current.get("rssi")
        current["uptime"] = _int_or_none(data.get("uptime")) if data.get("uptime") is not None else current.get("uptime")
        current["publish_interval"] = _float_or_none(data.get("publish_interval")) if data.get("publish_interval") is not None else current.get("publish_interval")
        current["firmware"] = data.get("firmware") or current.get("firmware")
        current["capabilities"] = _capabilities(data, current.get("capabilities"))
        current["topic_status"] = topic or current.get("topic_status")
        current["reason"] = data.get("reason")
        current["raw_status"] = deepcopy(data)

        _devices[str(device_id)] = current
        return deepcopy(current)


def get_mqtt_sensor_device(device_id):
    with _lock:
        device = _devices.get(str(device_id))
        return deepcopy(device) if device else None


def list_mqtt_sensor_devices():
    with _lock:
        return [
            deepcopy(_devices[key])
            for key in sorted(_devices)
        ]


def clear_mqtt_sensor_devices():
    """Nur für Tests."""
    with _lock:
        _devices.clear()
