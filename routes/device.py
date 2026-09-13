from copy import deepcopy
import time

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
from core.controller_states import resolve_control_state
from core.devices import (
    DeviceHardwareRequiredError,
    get_device_env_config,
    get_device_label,
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
from services.grow_events import enqueue_event


_DEVICE_STATE_LABELS = {
    "on": "Dauerbetrieb",
    "time": "Zeitsteuerung",
    "env": "ENV",
    "env_standby": "ENV-Standby",
    "interval_a": "Phase A · Tag",
    "interval_b": "Phase B · Tag",
    "interval_a_night": "Phase A · Nacht",
    "interval_b_night": "Phase B · Nacht",
}

_DEVICE_MODE_LABELS = {
    "OFF": "Deaktiviert",
    "ON": "Dauerbetrieb",
    "TIME": "Zeitsteuerung",
    "INTERVAL": "Intervall",
    "ENV": "Umweltregelung",
}


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
        "profile_schedule": {
            "day_start_min": int(runtime.config.get("DAY_START_MIN", 0)),
            "night_start_min": int(runtime.config.get("NIGHT_START_MIN", 0)),
        },

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


def _device_setting_snapshot(runtime, device, schema=None):
    """Normalisierte, freigegebene Gerätewerte für einen sicheren Diff."""
    params = deepcopy(get_device_params(device, runtime=runtime))
    env = deepcopy(get_device_env_config(device, runtime=runtime))
    schema = schema if isinstance(schema, dict) else {}
    values = {}

    def add(key, label, value, kind="value", unit=""):
        values[key] = {
            "label": label,
            "value": deepcopy(value),
            "kind": kind,
            "unit": unit,
        }

    add("mode", "Betriebsmodus", get_device_mode(device, runtime=runtime), "mode")
    add("start_min", "Startzeit", int(params.get("start_min", 0) or 0), "time")
    add("end_min", "Endzeit", int(params.get("end_min", 0) or 0), "time")
    add("interval_on", "Phase A · Dauer", int(params.get("interval_on", 300) or 0), "duration")
    add("interval_off", "Phase B · Dauer", int(params.get("interval_off", 900) or 0), "duration")
    add(
        "interval_night_enabled",
        "Eigenes Nachtprofil",
        bool(params.get("interval_night_enabled", False)),
        "switch",
    )
    add(
        "interval_night_on",
        "Phase A · Nacht · Dauer",
        int(params.get("interval_night_on", params.get("interval_on", 300)) or 0),
        "duration",
    )
    add(
        "interval_night_off",
        "Phase B · Nacht · Dauer",
        int(params.get("interval_night_off", params.get("interval_off", 900)) or 0),
        "duration",
    )

    for state_name, state_label in _DEVICE_STATE_LABELS.items():
        state = resolve_control_state(params, state_name)
        add(
            f"state.{state_name}.power",
            f"{state_label} · Shelly-Power",
            bool(state.get("power")),
            "switch",
        )
        controller = state.get("controller") or {}
        for setting_name, spec in schema.items():
            add(
                f"state.{state_name}.controller.{setting_name}",
                f"{state_label} · {spec.get('label') or setting_name}",
                controller.get(setting_name),
                "value",
                str(spec.get("unit") or ""),
            )

    add("env.use_temp", "Temperatur auswerten", bool(env.get("use_temp", False)), "switch")
    add("env.use_hum", "Feuchte auswerten", bool(env.get("use_hum", False)), "switch")
    add("env.logic", "ENV-Verknüpfung", str(env.get("logic", "OR") or "OR"), "choice")
    add("env.direction", "ENV-Richtung", str(env.get("direction", "HIGH") or "HIGH"), "choice")
    add("env.standby_enabled", "ENV-Standby", bool(env.get("standby_enabled", False)), "switch")
    return values


def _format_device_setting(item):
    value = item.get("value")
    kind = item.get("kind")
    if value is None:
        return "—"
    if kind == "mode":
        return _DEVICE_MODE_LABELS.get(str(value).upper(), str(value))
    if kind == "time":
        minutes = max(0, min(1439, int(value)))
        return f"{minutes // 60:02d}:{minutes % 60:02d} Uhr"
    if kind == "duration":
        minutes = float(value) / 60.0
        text = f"{minutes:.2f}".rstrip("0").rstrip(".").replace(".", ",")
        return f"{text} Min."
    if kind == "switch":
        return "Ein" if bool(value) else "Aus"
    if kind == "choice":
        return {
            "OR": "ODER",
            "AND": "UND",
            "HIGH": "oberhalb des Sollwerts",
            "LOW": "unterhalb des Sollwerts",
        }.get(str(value).upper(), str(value))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        text = f"{float(value):.3f}".rstrip("0").rstrip(".").replace(".", ",")
    else:
        text = str(value)
    unit = str(item.get("unit") or "")
    return f"{text} {unit}" if unit else text


def _enqueue_device_setting_change(runtime, device, before, after, payload=None):
    """Ein Speichervorgang ergibt höchstens eine kompakte Timeline-Karte."""
    changes = []
    for key in sorted(set(before) | set(after)):
        previous = before.get(key) or {}
        current = after.get(key) or {}
        if previous.get("value") == current.get("value"):
            continue
        descriptor = current or previous
        changes.append(
            f"{descriptor.get('label') or key}: "
            f"{_format_device_setting(previous)} → "
            f"{_format_device_setting(current)}"
        )

    if not changes:
        return False

    visible = changes[:4]
    summary = "; ".join(visible)
    if len(changes) > len(visible):
        summary += f"; +{len(changes) - len(visible)} weitere Änderung(en)"
    summary += "."

    label = get_device_label(device, runtime=runtime)
    metadata = {"gerät": device, "geändert": len(changes)}
    for index, change in enumerate(changes[:8], start=1):
        metadata[f"änderung_{index}"] = change
    apply_status = ((payload or {}).get("controller_apply") or {}).get("status")
    if apply_status:
        metadata["controller_status"] = apply_status

    occurred_at = int(time.time())
    return enqueue_event(
        station_id=runtime.tent_id,
        occurred_at=occurred_at,
        category="device",
        event_type="device_settings_updated",
        severity="info",
        title=f"Geräteeinstellungen geändert: {label}",
        summary=summary,
        source="device_config",
        source_id=device,
        dedupe_key=(
            f"device-setting:{runtime.tent_id}:{device}:{time.time_ns()}"
        ),
        metadata=metadata,
    )


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

    schema = (_controller_context(runtime, device).get("schema") or {})
    settings_before = _device_setting_snapshot(
        runtime,
        device,
        schema=schema,
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

    settings_after = _device_setting_snapshot(
        runtime,
        device,
        schema=schema,
    )
    try:
        _enqueue_device_setting_change(
            runtime,
            device,
            settings_before,
            settings_after,
            payload,
        )
    except Exception as exc:
        # Konfigurationsspeicherung bleibt unabhängig von der Timeline.
        print("⚠️ Geräteänderung konnte nicht an Grow Intelligence übergeben werden:", exc)

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
