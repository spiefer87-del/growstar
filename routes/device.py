from copy import deepcopy

from flask import jsonify, request

from core.capability_routing import (
    controller_assignment_for_config,
    spiderfarmer_control_targets,
)
from core.controller_setpoints import (
    controller_schema,
    normalize_controller_setpoints,
    stored_controller_setpoints,
)
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
from core.vpd import vpd_device_context
from services.spiderfarmer_commands import send_controller_setpoints


class VpdDeviceLockedError(RuntimeError):
    """Ein ENV-Aktor ist während AUTO ausschließlich dem VPD-Regler zugeordnet."""

    def __init__(self, device, context):
        self.device = str(device)
        self.context = deepcopy(context or {})
        super().__init__(
            "Dieses Gerät wird gerade von VPD intelligent gesteuert. "
            "Bitte zuerst unter Klima & Grenzwerte den Automatik-Modus verlassen."
        )


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


def _controller_context(runtime, device):
    assignment = controller_assignment_for_config(
        runtime.config,
        device,
    )

    if not isinstance(assignment, dict) or not assignment.get("target_id"):
        return {
            "assigned": False,
            "target_id": None,
            "provider": None,
            "label": None,
            "online": None,
            "family": None,
            "capabilities": [],
            "schema": {},
            "setpoints": stored_controller_setpoints(
                get_device_params(device, runtime=runtime)
            ),
            "command_transport_enabled": False,
        }

    target_id = str(assignment.get("target_id") or "")
    target = next(
        (
            item
            for item in spiderfarmer_control_targets()
            if str(item.get("id") or "") == target_id
        ),
        None,
    )

    if not isinstance(target, dict):
        return {
            "assigned": True,
            "target_id": target_id,
            "provider": assignment.get("provider"),
            "label": target_id,
            "online": False,
            "family": None,
            "capabilities": [],
            "schema": {},
            "setpoints": stored_controller_setpoints(
                get_device_params(device, runtime=runtime)
            ),
            "command_transport_enabled": False,
            "missing_target": True,
        }

    schema = controller_schema(target)

    return {
        "assigned": True,
        "target_id": target_id,
        "provider": target.get("provider"),
        "label": target.get("label") or target_id,
        "online": bool(target.get("online")),
        "family": target.get("family"),
        "capabilities": list(target.get("capabilities") or []),
        "schema": schema,
        "setpoints": stored_controller_setpoints(
            get_device_params(device, runtime=runtime)
        ),
        "command_transport_enabled": False,
    }


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

        # SF.4C: generische Controller-Zuordnung + lokale Sollwerte.
        # command_transport_enabled bleibt absichtlich False.
        "controller": _controller_context(runtime, device),

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
        "vpd_control": vpd_device_context(device, runtime=runtime),
    }


def _normalize_device_update(runtime, device, data):
    if not isinstance(data, dict):
        raise TypeError("Geräte-Update muss ein JSON-Objekt sein")

    working = deepcopy(data)

    if "controller_setpoints" not in working:
        return working

    context = _controller_context(runtime, device)
    normalized = normalize_controller_setpoints(
        working.pop("controller_setpoints"),
        context.get("schema") or {},
    )

    params = working.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise TypeError("params muss ein JSON-Objekt sein")

    params = deepcopy(params)

    # Preserve only normalized, controller-generic desired values.
    params["controller"] = normalized
    working["params"] = params

    return working


def _save_device(runtime, device, data):
    vpd_context = vpd_device_context(device, runtime=runtime)
    if vpd_context.get("locked"):
        raise VpdDeviceLockedError(device, vpd_context)

    normalized = _normalize_device_update(
        runtime,
        device,
        data,
    )

    requested_setpoints = (
        deepcopy(data.get("controller_setpoints"))
        if isinstance(data, dict)
        and isinstance(data.get("controller_setpoints"), dict)
        else None
    )

    changed = update_device_config(
        device,
        normalized,
        runtime=runtime,
    )

    payload = _device_payload(runtime, device)
    payload["changed"] = changed

    if requested_setpoints is not None:
        context = payload.get("controller") or {}

        if not context.get("assigned"):
            payload["controller_apply"] = {
                "success": False,
                "status": "not_assigned",
                "message": "Kein Controller-Gerät zugeordnet.",
            }
        elif context.get("provider") != "spiderfarmer":
            payload["controller_apply"] = {
                "success": False,
                "status": "unsupported_provider",
                "message": (
                    "Der zugeordnete Controller-Provider besitzt noch keinen "
                    "Growstar-Schreibadapter."
                ),
            }
        else:
            target_id = str(context.get("target_id") or "")
            parts = target_id.split(":", 2)
            controller_id = parts[1] if len(parts) >= 3 else ""
            module = parts[2] if len(parts) >= 3 else ""
            pid = ""

            for target in spiderfarmer_control_targets():
                if str(target.get("id") or "") == target_id:
                    pid = str(target.get("controller_pid") or "")
                    module = str(target.get("device_id") or module)
                    break

            try:
                payload["controller_apply"] = send_controller_setpoints(
                    controller_id=controller_id,
                    pid=pid,
                    module=module,
                    setpoints=requested_setpoints,
                )
            except Exception as exc:
                payload["controller_apply"] = {
                    "success": False,
                    "status": "bridge_error",
                    "message": str(exc),
                }

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


def _vpd_locked_response(exc):
    return jsonify(
        success=False,
        error="vpd_device_locked",
        message=str(exc),
        device=exc.device,
        vpd_control=exc.context,
    ), 423


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
        except VpdDeviceLockedError as exc:
            return _vpd_locked_response(exc)
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
        except VpdDeviceLockedError as exc:
            return _vpd_locked_response(exc)
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
        except VpdDeviceLockedError as exc:
            return _vpd_locked_response(exc)
        except DeviceHardwareRequiredError as exc:
            return _hardware_required_response(exc)
        except (TypeError, ValueError) as exc:
            return jsonify(success=False, error=str(exc)), 400
