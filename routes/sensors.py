from flask import jsonify, request

import core.state as state

from core.config import config, save_config
from core.sensors import apply_sensor_assignments

from services.hardware import hardware


def _sensor_options():

    temperature = [
        {
            "source": "legacy",
            "device_id": None,
            "property": "temperature",
            "label": "Alter Sensor",
            "value": state.live_state.get("temp")
        }
    ]

    humidity = [
        {
            "source": "legacy",
            "device_id": None,
            "property": "humidity",
            "label": "Alter Sensor",
            "value": state.live_state.get("hum")
        }
    ]

    try:

        devices = hardware.devices()

    except Exception:

        devices = []

    for device in devices:

        props = device.properties or {}

        if device.type != "sensor":

            continue

        label = (
            device.name
            or device.model
            or device.id
        )

        if props.get("gateway_ip"):

            label += (
                " · " +
                props.get("gateway_ip")
            )

        temperature.append(
            {
                "source": "hardware_device",
                "device_id": device.id,
                "property": "temperature",
                "label": label,
                "value": props.get("temperature")
            }
        )

        humidity.append(
            {
                "source": "hardware_device",
                "device_id": device.id,
                "property": "humidity",
                "label": label,
                "value": props.get("humidity")
            }
        )

    return {
        "temperature": temperature,
        "humidity": humidity
    }


def _normalize_assignment(sensor_name, data):

    source = data.get(
        "source",
        "legacy"
    )

    if source == "hardware_device":

        device_id = data.get(
            "device_id"
        )

        prop = data.get(
            "property"
        )

        if not prop:

            prop = (
                "temperature"
                if sensor_name == "temperature"
                else "humidity"
            )

        label = data.get(
            "label",
            "Hardware Sensor"
        )

        return {
            "source": "hardware_device",
            "device_id": device_id,
            "property": prop,
            "label": label
        }

    return {
        "source": "legacy",
        "device_id": None,
        "property": (
            "temperature"
            if sensor_name == "temperature"
            else "humidity"
        ),
        "label": "Alter Sensor"
    }


def register(app):

    @app.get("/api/sensors/assignments")
    def get_sensor_assignments():

        config.setdefault(
            "SENSOR_ASSIGNMENTS",
            {
                "temperature": {
                    "source": "legacy",
                    "device_id": None,
                    "property": "temperature",
                    "label": "Alter Sensor"
                },
                "humidity": {
                    "source": "legacy",
                    "device_id": None,
                    "property": "humidity",
                    "label": "Alter Sensor"
                }
            }
        )

        return jsonify({
            "success": True,
            "assignments": config.get(
                "SENSOR_ASSIGNMENTS",
                {}
            ),
            "options": _sensor_options()
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

        changed = apply_sensor_assignments(
            force=True
        )

        return jsonify({
            "success": True,
            "assignments": config["SENSOR_ASSIGNMENTS"],
            "changed": changed,
            "state": state.live_state
        })


    @app.post("/api/sensors/apply")
    def apply_sensors():

        changed = apply_sensor_assignments(
            force=True
        )

        return jsonify({
            "success": True,
            "changed": changed,
            "state": state.live_state
        })
