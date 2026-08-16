from copy import deepcopy

from flask import jsonify, request

from core.devices import (
    DeviceHardwareRequiredError,
    get_device_env_config,
    get_device_mode,
    get_device_params,
    update_device_config,
    validate_device_name,
)
from core.hardware.actuator_health import get_endpoint_health
from core.hardware_assignments import device_assignment
from core.runtime import get_default_runtime, get_runtime
from core.safety import get_runtime_safety_snapshot
from core.tents import manager as tent_manager, validate_tent_id


def _validate_device(device):
    try:
        return validate_device_name(device), None
    except ValueError:
        return None, (jsonify(success=False, error="device_not_found"), 404)


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


def _device_payload(runtime, device):
    state = runtime.state
    mode = get_device_mode(device, runtime=runtime)
    params = deepcopy(get_device_params(device, runtime=runtime))
    env = deepcopy(get_device_env_config(device, runtime=runtime))
    assignment = device_assignment(runtime.tent_id, device)

    safety = get_runtime_safety_snapshot(runtime)
    safety_device = deepcopy((safety.get("devices") or {}).get(device) or {})
    safety_override = deepcopy((safety.get("overrides") or {}).get(device) or {})

    hardware_health = None
    if assignment.get("configured"):
        hardware_health = get_endpoint_health(
            assignment["ip"],
            assignment["relay"],
        )

    with runtime.state_lock:
        runtime_on = bool(getattr(state, f"{device}_on", False))
        shadow_desired = runtime.shadow_outputs.get(device)

    physical_known = bool(
        hardware_health
        and hardware_health.get("state") == "ok"
        and isinstance(hardware_health.get("actual_state"), bool)
    )
    physical_on = hardware_health.get("actual_state") if physical_known else None

    return {
        "success": True,
        "tent_id": runtime.tent_id,
        "device": device,
        "mode": mode,
        "params": params,
        "env_config": env,

        # Rückwärtskompatibel + explizit diagnostisch.
        "actual_on": runtime_on,
        "runtime_on": runtime_on,

        # Verifizierte Hardware-Wahrheit.
        "assignment": assignment,
        "hardware_configured": bool(assignment.get("configured")),
        "hardware_health": hardware_health,
        "physical_known": physical_known,
        "physical_on": physical_on,

        "shadow_desired": shadow_desired,
        "control_enabled": runtime.control_enabled,
        "shadow_enabled": runtime.shadow_enabled,
        "hardware_actuation_blocked": not runtime.control_enabled,

        "safety": {
            "active": bool(safety.get("active")),
            "stale": bool(safety.get("stale")),
            "reason": safety.get("reason"),
            "device": safety_device,
            "override": safety_override,
            "blocked": device in (safety.get("blocked_devices") or []),
        },
    }


def _save_device(runtime, device, data):
    changed = update_device_config(device, data, runtime=runtime)
    payload = _device_payload(runtime, device)
    payload["changed"] = changed
    return payload


def _hardware_required_response(exc):
    return jsonify(
        success=False,
        error="device_hardware_required",
        message=str(exc),
        device=exc.device,
        mode=exc.mode,
        assignment=exc.assignment,
    ), 409


def register(app):

    @app.route("/api/device/<device>", methods=["GET", "POST"])
    def api_device(device):
        device, error = _validate_device(device)
        if error:
            return error
        runtime = get_default_runtime()
        if request.method == "GET":
            return jsonify(_device_payload(runtime, device))
        data = request.get_json(silent=True) or {}
        try:
            return jsonify(_save_device(runtime, device, data))
        except DeviceHardwareRequiredError as exc:
            return _hardware_required_response(exc)
        except (TypeError, ValueError) as exc:
            return jsonify(success=False, error=str(exc)), 400

    @app.route("/api/device/mode/<device>", methods=["POST"])
    def api_set_device_mode(device):
        device, error = _validate_device(device)
        if error:
            return error
        runtime = get_default_runtime()
        data = request.get_json(silent=True) or {}
        try:
            return jsonify(_save_device(runtime, device, data))
        except DeviceHardwareRequiredError as exc:
            return _hardware_required_response(exc)
        except (TypeError, ValueError) as exc:
            return jsonify(success=False, error=str(exc)), 400

    @app.route("/api/tents/<tent_id>/devices/<device>", methods=["GET", "POST"])
    def api_tent_device(tent_id, device):
        device, error = _validate_device(device)
        if error:
            return error
        runtime, error = _find_runtime(tent_id)
        if error:
            return error
        if request.method == "GET":
            return jsonify(_device_payload(runtime, device))
        data = request.get_json(silent=True) or {}
        try:
            return jsonify(_save_device(runtime, device, data))
        except DeviceHardwareRequiredError as exc:
            return _hardware_required_response(exc)
        except (TypeError, ValueError) as exc:
            return jsonify(success=False, error=str(exc)), 400
