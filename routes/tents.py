# routes/tents.py

import time

from flask import jsonify, request

from core.config_update import apply_config_patch, config_snapshot
from core.devices import DEVICE_NAMES, get_device_mode
from core.profile import PROFILES, apply_profile, get_active_profile
from core.runtime import get_runtime, list_runtimes
from core.tents import manager as tent_manager, validate_tent_id


_DEVICE_NAMES = DEVICE_NAMES

_STATION_CONFIG_FORBIDDEN_KEYS = {
    "SENSOR_ASSIGNMENTS",
    "TEMP_OFFSET",
    "HUM_OFFSET",
    "DEVICE_MODES",
    "DEVICE_PARAMS",
    "DEVICE_ENV_CONFIG",
}


def _validate_station_config_patch(data):
    if not isinstance(data, dict):
        raise TypeError("Config-Update muss ein JSON-Objekt sein")

    forbidden = [
        key for key in data
        if key in _STATION_CONFIG_FORBIDDEN_KEYS
        or key.startswith("IP_")
        or key.startswith("RELAY_")
    ]
    if forbidden:
        raise ValueError(
            "Diese Einstellungen besitzen einen eigenen stationsbezogenen "
            "Endpunkt: " + ", ".join(sorted(forbidden))
        )


def _runtime_map():
    return {runtime.tent_id: runtime for runtime in list_runtimes()}


def _find_runtime(tent_id):
    try:
        tent_id = validate_tent_id(tent_id)
    except ValueError:
        return None, (jsonify(success=False, error="invalid_tent_id"), 400)

    tent = tent_manager.get(tent_id)
    if tent is None:
        return None, (jsonify(success=False, error="tent_not_found"), 404)

    try:
        return get_runtime(tent_id), None
    except KeyError:
        return None, (
            jsonify(
                success=False,
                error="tent_runtime_not_loaded",
                tent=tent,
            ),
            409,
        )


def _age(last_seen):
    if not last_seen:
        return None
    return max(0, int(time.time() - last_seen))


def _state_snapshot(runtime):
    st = runtime.state
    cfg = runtime.config

    with runtime.state_lock:
        live = dict(st.live_state)
        shadow_outputs = dict(runtime.shadow_outputs)

    devices = {}
    for device in _DEVICE_NAMES:
        devices[device] = {
            "actual_on": getattr(st, f"{device}_on", False),
            "mode": get_device_mode(device, runtime=runtime),
            "shadow_desired": shadow_outputs.get(device),
        }

    return {
        "tent_id": runtime.tent_id,
        "name": runtime.name,
        "enabled": runtime.enabled,
        "controller_id": runtime.controller_id,
        "runtime_mode": runtime.loop_mode,
        "last_loop_ts": runtime.last_loop_ts,
        "control_enabled": runtime.control_enabled,
        "shadow_enabled": runtime.shadow_enabled,
        "hardware_actuation_blocked": not runtime.control_enabled,

        # Sensoren / Sollwerte
        "temp_raw": live.get("temp_raw"),
        "temp": live.get("temp"),
        "hum_raw": live.get("hum_raw"),
        "hum": live.get("hum"),
        "vpd": live.get("vpd"),
        "temp_target": live.get("temp_target"),
        "temp_tol": live.get("temp_tol"),
        "hum_target": live.get("hum_target"),
        "hum_tol": live.get("hum_tol"),
        "temp_source": live.get("temp_source"),
        "hum_source": live.get("hum_source"),
        "sensor_assignments": live.get(
            "sensor_assignments",
            cfg.get("SENSOR_ASSIGNMENTS", {}),
        ),

        # Profil / Rampe
        "profile": st.current_profile,
        "active_profile": get_active_profile(runtime=runtime),
        "ramp_active": bool(
            st.ramp_active and cfg.get("RAMP_ENABLED", 0)
        ),
        "ramp_target": live.get("ramp_target"),

        # Sensorzustand
        "temp_ok": not st.temp_stale,
        "hum_ok": not st.hum_stale,
        "temp_age": _age(st.last_ds_time),
        "hum_age": _age(st.last_dht_time),

        # Reale vs. nur berechnete Ausgänge
        "devices": devices,
        "shadow_outputs": shadow_outputs,
        "device_modes": cfg.get("DEVICE_MODES", {}),

        # Energie bleibt vorerst Runtime-lokal/leer für zusätzliche Stationen.
        "energy": dict(runtime.energy_state),
    }


def _config_payload(runtime):
    return {
        "success": True,
        "tent_id": runtime.tent_id,
        "name": runtime.name,
        "control_enabled": runtime.control_enabled,
        "shadow_enabled": runtime.shadow_enabled,
        "hardware_actuation_blocked": not runtime.control_enabled,
        "active_profile": get_active_profile(runtime=runtime),
        "profiles": sorted((PROFILES.get("profiles") or {}).keys()),
        "config": config_snapshot(runtime),
    }


def register(app):
    """Generische Multi-Station-API für beliebig viele lokale Runtimes."""

    @app.route("/api/tents", methods=["GET"])
    def api_tents():
        runtimes = _runtime_map()
        result = []

        for tent in tent_manager.list_tents():
            runtime = runtimes.get(tent["id"])
            item = dict(tent)
            item.update({
                "runtime_loaded": runtime is not None,
                "runtime_mode": runtime.loop_mode if runtime else "unloaded",
                "last_loop_ts": runtime.last_loop_ts if runtime else None,
                "hardware_actuation_blocked": (
                    not runtime.control_enabled if runtime else True
                ),
            })

            if runtime is not None:
                with runtime.state_lock:
                    item["temp"] = runtime.state.live_state.get("temp")
                    item["hum"] = runtime.state.live_state.get("hum")
                    item["vpd"] = runtime.state.live_state.get("vpd")

            result.append(item)

        return jsonify({
            "success": True,
            "default_tent_id": tent_manager.default_tent_id(),
            "tents": result,
        })

    @app.route("/api/tents/<tent_id>/state", methods=["GET"])
    def api_tent_state(tent_id):
        runtime, error = _find_runtime(tent_id)
        if error:
            return error
        return jsonify(_state_snapshot(runtime))

    @app.route("/api/tents/<tent_id>/config", methods=["GET", "POST"])
    def api_tent_config(tent_id):
        runtime, error = _find_runtime(tent_id)
        if error:
            return error

        if request.method == "GET":
            return jsonify(_config_payload(runtime))

        data = request.get_json(silent=True) or {}
        try:
            _validate_station_config_patch(data)
            result = apply_config_patch(data, runtime=runtime)
        except (TypeError, ValueError) as exc:
            return jsonify(success=False, error=str(exc)), 400

        payload = _config_payload(runtime)
        payload["changed_keys"] = result["changed_keys"]
        return jsonify(payload)

    @app.route("/api/tents/<tent_id>/profile/<name>", methods=["POST"])
    def api_tent_profile(tent_id, name):
        runtime, error = _find_runtime(tent_id)
        if error:
            return error

        if not apply_profile(name, runtime=runtime):
            return jsonify(
                success=False,
                error="profile_not_found",
                profile=name,
            ), 404

        return jsonify(_config_payload(runtime))
