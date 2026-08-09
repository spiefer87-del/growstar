from copy import deepcopy

from flask import jsonify, request

from core.devices import (
    DEVICE_NAMES,
    get_device_env_config,
    get_device_mode,
    get_device_params,
    update_device_config,
    validate_device_name,
)
from core.runtime import get_default_runtime, get_runtime
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

    with runtime.state_lock:
        actual_on = bool(getattr(state, f"{device}_on", False))
        shadow_desired = runtime.shadow_outputs.get(device)

    return {
        "success": True,
        "tent_id": runtime.tent_id,
        "device": device,
        "mode": mode,
        "params": params,
        "env_config": env,
        "actual_on": actual_on,
        "shadow_desired": shadow_desired,
        "control_enabled": runtime.control_enabled,
        "shadow_enabled": runtime.shadow_enabled,
        "hardware_actuation_blocked": not runtime.control_enabled,
    }


def _save_device(runtime, device, data):
    changed = update_device_config(device, data, runtime=runtime)
    payload = _device_payload(runtime, device)
    payload["changed"] = changed
    return payload


def register(app):

    # ------------------------------------------------------------------
    # Legacy tent_1 API
    # ------------------------------------------------------------------

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
        except (TypeError, ValueError) as exc:
            return jsonify(success=False, error=str(exc)), 400

    # ------------------------------------------------------------------
    # Generische Multi-Station API
    # ------------------------------------------------------------------

    @app.route(
        "/api/tents/<tent_id>/devices/<device>",
        methods=["GET", "POST"],
    )
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
        except (TypeError, ValueError) as exc:
            return jsonify(success=False, error=str(exc)), 400
