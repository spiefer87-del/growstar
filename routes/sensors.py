# routes/sensors.py

from flask import jsonify, request

from core.runtime import get_default_runtime, get_runtime
from core.sensor_sources import (
    apply_sensor_assignments,
    list_sensor_sources,
    update_sensor_source,
)
from core.tents import manager as tent_manager, validate_tent_id
from services.hardware import hardware


_OFFSET_KEYS = ("TEMP_OFFSET", "HUM_OFFSET")


def _default_assignments():
    return {
        "temperature": {
            "source_id": "mqtt:ds18b20",
            "field": "temperature",
            "label": "Alter Temperatursensor",
        },
        "humidity": {
            "source_id": "mqtt:dht22",
            "field": "humidity",
            "label": "Alter Feuchtesensor",
        },
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

        source_id = "hardware:" + device.id
        label = (
            device.name
            or props.get("local_name")
            or device.model
            or device.id
        )

        if props.get("gateway_ip"):
            label += " · " + props.get("gateway_ip")

        update_sensor_source(
            source_id,
            label=label,
            source_type="hardware",
            temperature=props.get("temperature"),
            humidity=props.get("humidity"),
            battery=props.get("battery"),
            rssi=props.get("rssi"),
            raw=device.to_dict(),
        )

        sources.append({
            "id": source_id,
            "label": label,
            "type": "hardware",
            "temperature": props.get("temperature"),
            "humidity": props.get("humidity"),
            "battery": props.get("battery"),
            "rssi": props.get("rssi"),
            "last_seen": props.get("last_seen"),
        })

    return sources


def _sensor_options():
    """Controller-weite Quellen; Zuweisung erfolgt erst pro Runtime."""

    sources = {}

    for source in list_sensor_sources():
        source_id = source.get("id")
        if source_id:
            sources[source_id] = source

    sources.setdefault(
        "mqtt:ds18b20",
        {
            "id": "mqtt:ds18b20",
            "label": "Alter Temperatursensor",
            "type": "mqtt",
            "temperature": None,
            "humidity": None,
            "battery": None,
            "rssi": None,
        },
    )
    sources.setdefault(
        "mqtt:dht22",
        {
            "id": "mqtt:dht22",
            "label": "Alter Feuchtesensor",
            "type": "mqtt",
            "temperature": None,
            "humidity": None,
            "battery": None,
            "rssi": None,
        },
    )

    for source in _hardware_sources():
        source_id = source.get("id")
        if not source_id:
            continue
        existing = sources.get(source_id, {})
        existing.update(source)
        sources[source_id] = existing

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
                "type": source.get("type"),
            })

        if source.get("humidity") is not None or source_id == "mqtt:dht22":
            humidity.append({
                "source_id": source_id,
                "field": "humidity",
                "label": label,
                "value": source.get("humidity"),
                "type": source.get("type"),
            })

    return {
        "temperature": temperature,
        "humidity": humidity,
    }


def _normalize_assignment(sensor_name, data):
    if not isinstance(data, dict):
        raise TypeError(f"{sensor_name} muss ein JSON-Objekt sein")

    source_id = data.get("source_id")
    field = data.get("field")
    label = data.get("label")

    if not source_id:
        raise ValueError(f"source_id für {sensor_name} fehlt")

    if not field:
        field = "temperature" if sensor_name == "temperature" else "humidity"

    return {
        "source_id": str(source_id),
        "field": str(field),
        "label": str(label or source_id),
    }


def _find_runtime(tent_id):
    try:
        tent_id = validate_tent_id(tent_id)
    except ValueError:
        return None, (jsonify(success=False, error="invalid_tent_id"), 400)

    if tent_manager.get(tent_id) is None:
        return None, (jsonify(success=False, error="tent_not_found"), 404)

    try:
        return get_runtime(tent_id), None
    except KeyError:
        return None, (jsonify(success=False, error="tent_runtime_not_loaded"), 409)


def _offsets(runtime):
    return {
        "TEMP_OFFSET": float(runtime.config.get("TEMP_OFFSET", 0.0) or 0.0),
        "HUM_OFFSET": float(runtime.config.get("HUM_OFFSET", 0.0) or 0.0),
    }


def _assignments_payload(runtime):
    runtime.config.setdefault("SENSOR_ASSIGNMENTS", {})
    return {
        "success": True,
        "tent_id": runtime.tent_id,
        "assignments": runtime.config.get("SENSOR_ASSIGNMENTS", {}),
        "offsets": _offsets(runtime),
        "options": _sensor_options(),
        "sources": list_sensor_sources(),
    }


def _save_assignments(runtime, data):
    if not isinstance(data, dict):
        raise TypeError("Sensor-Update muss ein JSON-Objekt sein")

    # Atomar in einer Kopie arbeiten. Dadurch kann ein fehlerhaftes zweites
    # Feld keine halbfertige Sensorzuweisung im Regelkreis hinterlassen.
    current_assignments = runtime.config.get("SENSOR_ASSIGNMENTS", {})
    assignments = dict(current_assignments) if isinstance(current_assignments, dict) else {}

    if "temperature" in data:
        assignments["temperature"] = _normalize_assignment(
            "temperature",
            data["temperature"],
        )

    if "humidity" in data:
        assignments["humidity"] = _normalize_assignment(
            "humidity",
            data["humidity"],
        )

    offsets = data.get("offsets", {})
    if offsets is None:
        offsets = {}
    if not isinstance(offsets, dict):
        raise TypeError("offsets muss ein JSON-Objekt sein")

    new_offsets = {}
    for key in _OFFSET_KEYS:
        raw = offsets.get(key, data.get(key))
        if raw is None:
            continue
        try:
            new_offsets[key] = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} muss numerisch sein") from exc

    if "temperature" in data or "humidity" in data:
        runtime.config["SENSOR_ASSIGNMENTS"] = assignments
    for key, value in new_offsets.items():
        runtime.config[key] = value

    runtime.persist_config()
    changed = apply_sensor_assignments(runtime=runtime)

    with runtime.state_lock:
        state_snapshot = dict(runtime.state.live_state)

    return {
        "success": True,
        "tent_id": runtime.tent_id,
        "assignments": runtime.config.get("SENSOR_ASSIGNMENTS", {}),
        "offsets": _offsets(runtime),
        "changed": changed,
        "state": state_snapshot,
    }


def register(app):

    # ------------------------------------------------------------------
    # Legacy tent_1 API
    # ------------------------------------------------------------------

    @app.get("/api/sensors/assignments")
    def get_sensor_assignments():
        return jsonify(_assignments_payload(get_default_runtime()))

    @app.post("/api/sensors/assignments")
    def save_sensor_assignments():
        data = request.get_json(silent=True) or {}
        try:
            return jsonify(_save_assignments(get_default_runtime(), data))
        except (TypeError, ValueError) as exc:
            return jsonify(success=False, error=str(exc)), 400

    @app.post("/api/sensors/apply")
    def apply_sensors():
        runtime = get_default_runtime()
        changed = apply_sensor_assignments(runtime=runtime)
        with runtime.state_lock:
            snapshot = dict(runtime.state.live_state)
        return jsonify({
            "success": True,
            "tent_id": runtime.tent_id,
            "changed": changed,
            "state": snapshot,
        })

    # ------------------------------------------------------------------
    # Generische Multi-Station API
    # ------------------------------------------------------------------

    @app.route(
        "/api/tents/<tent_id>/sensors/assignments",
        methods=["GET", "POST"],
    )
    def api_tent_sensor_assignments(tent_id):
        runtime, error = _find_runtime(tent_id)
        if error:
            return error

        if request.method == "GET":
            return jsonify(_assignments_payload(runtime))

        data = request.get_json(silent=True) or {}
        try:
            return jsonify(_save_assignments(runtime, data))
        except (TypeError, ValueError) as exc:
            return jsonify(success=False, error=str(exc)), 400

    @app.post("/api/tents/<tent_id>/sensors/apply")
    def api_tent_sensors_apply(tent_id):
        runtime, error = _find_runtime(tent_id)
        if error:
            return error

        changed = apply_sensor_assignments(runtime=runtime)
        with runtime.state_lock:
            snapshot = dict(runtime.state.live_state)

        return jsonify({
            "success": True,
            "tent_id": runtime.tent_id,
            "changed": changed,
            "state": snapshot,
        })
