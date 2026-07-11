# routes/sensors.py

from flask import jsonify, request

import core.state as state

from core.config import config, save_config

from core.sensor_sources import (
    list_sensor_sources,
    update_sensor_source,
    apply_sensor_assignments,
)

from services.hardware import hardware


def _default_assignments():

    return {
        "temperature": {
            "source_id": "mqtt:ds18b20",
            "field": "temperature",
            "label": "Alter Temperatursensor"
        },
        "humidity": {
            "source_id": "mqtt:dht22",
            "field": "humidity",
            "label": "Alter Feuchtesensor"
        }
    }


def _hardware_sources():

    sources = []

    try:

        devices = hardware.devices()

    except Exception:

        devices = []

    for device in devices:

        props = device.properties or {}

        if device.type != "sensor":

            continue

        source_id = (
            "hardware:" +
            device.id
        )

        label = (
            device.name
            or props.get("local_name")
            or device.model
            or device.id
        )

        if props.get("gateway_ip"):

            label += (
                " · " +
                props.get("gateway_ip")
            )

        # Hardware-Sensor auch als Quelle veröffentlichen,
        # falls er schon Werte hat.
        update_sensor_source(
            source_id,
            label=label,
            source_type="hardware",
            temperature=props.get("temperature"),
            humidity=props.get("humidity"),
            battery=props.get("battery"),
            rssi=props.get("rssi"),
            raw=device.to_dict()
        )

        sources.append({
            "id": source_id,
            "label": label,
            "type": "hardware",
            "temperature": props.get("temperature"),
            "humidity": props.get("humidity"),
            "battery": props.get("battery"),
            "rssi": props.get("rssi"),
            "last_seen": props.get("last_seen")
        })

    return sources


def _sensor_options():

    # Alte MQTT-Quellen immer anbieten
    update_sensor_source(
        "mqtt:ds18b20",
        label="Alter Temperatursensor",
        source_type="mqtt",
        temperature=state.live_state.get("legacy_temp_raw")
        or state.live_state.get("temp_raw")
    )

    update_sensor_source(
        "mqtt:dht22",
        label="Alter Feuchtesensor",
        source_type="mqtt",
        humidity=state.live_state.get("legacy_hum_raw")
        or state.live_state.get("hum_raw")
    )

    sources = {}

    for source in list_sensor_sources():

        sources[source.get("id")] = source

    for source in _hardware_sources():

        sources[source.get("id")] = source

    temperature = []
    humidity = []

    for source in sources.values():

        source_id = source.get("id")
        label = source.get("label") or source_id

        if source.get("temperature") is not None or source_id == "mqtt:ds18b20":

            temperature.append({
                "source_id": source_id,
                "field": "temperature",
                "label": label,
                "value": source.get("temperature"),
                "type": source.get("type")
            })

        if source.get("humidity") is not None or source_id == "mqtt:dht22":

            humidity.append({
                "source_id": source_id,
                "field": "humidity",
                "label": label,
                "value": source.get("humidity"),
                "type": source.get("type")
            })

    return {
        "temperature": temperature,
        "humidity": humidity
    }


def _normalize_assignment(sensor_name, data):

    source_id = data.get(
        "source_id"
    )

    field = data.get(
        "field"
    )

    label = data.get(
        "label"
    )

    if not source_id:

        defaults = _default_assignments()

        return defaults.get(
            sensor_name
        )

    if not field:

        field = (
            "temperature"
            if sensor_name == "temperature"
            else "humidity"
        )

    if not label:

        label = source_id

    return {
        "source_id": source_id,
        "field": field,
        "label": label
    }


def register(app):

    @app.get("/api/sensors/assignments")
    def get_sensor_assignments():

        config.setdefault(
            "SENSOR_ASSIGNMENTS",
            _default_assignments()
        )

        return jsonify({
            "success": True,
            "assignments": config.get(
                "SENSOR_ASSIGNMENTS",
                {}
            ),
            "options": _sensor_options(),
            "sources": list_sensor_sources()
        })


    @app.post("/api/sensors/assignments")
    def save_sensor_assignments():

        data = request.get_json(
            silent=True
        ) or {}

        temperature = _normalize_assignment(
            "temperature",
            data.get(
                "temperature",
                {}
            )
        )

        humidity = _normalize_assignment(
            "humidity",
            data.get(
                "humidity",
                {}
            )
        )

        config["SENSOR_ASSIGNMENTS"] = {
            "temperature": temperature,
            "humidity": humidity
        }

        save_config(
            config
        )

        changed = apply_sensor_assignments()

        return jsonify({
            "success": True,
            "assignments": config["SENSOR_ASSIGNMENTS"],
            "changed": changed,
            "state": state.live_state
        })


    @app.post("/api/sensors/apply")
    def apply_sensors():

        changed = apply_sensor_assignments()

        return jsonify({
            "success": True,
            "changed": changed,
            "state": state.live_state
        })
