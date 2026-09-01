import time

from flask import jsonify, request

from core.capability_routing import controller_assignment_for_config
from core.config_update import apply_config_patch, config_snapshot
from core.controller_setpoints import stored_controller_setpoints
from core.controller_states import resolve_control_state
from core.devices import DEVICE_NAMES, get_device_mode
from core.hardware.actuator_health import get_endpoint_health
from core.hardware_assignments import (
    HardwareAssignmentActiveModeError,
    HardwareAssignmentNotSafeOffError,
    HardwareConflictError,
    device_assignment,
    hardware_snapshot,
    update_hardware_assignments,
)
from core.profile import (
    PROFILE_SETTING_KEYS,
    PROFILES,
    ProfileActivationError,
    apply_profile,
    get_active_profile,
    profile_catalog,
    profile_settings_from_config,
    update_profile,
)
from core.live_preflight import evaluate_live_preflight
from core.runtime import get_runtime, list_runtimes
from core.safety import get_runtime_safety_snapshot
from core.tent_config import ensure_tent_config
from core.tents import manager as tent_manager, validate_tent_id
from services.live_control import LiveTransitionError, request_live, request_shadow
from services.spiderfarmer import device as spiderfarmer_device
from core.sensor_sources import get_sensor_source


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


def _find_tent(tent_id):
    try:
        tent_id = validate_tent_id(tent_id)
    except ValueError:
        return None, (jsonify(success=False, error="invalid_tent_id"), 400)

    tent = tent_manager.get(tent_id)
    if tent is None:
        return None, (jsonify(success=False, error="tent_not_found"), 404)
    return tent, None


def _age(last_seen):
    if not last_seen:
        return None
    return max(0, int(time.time() - last_seen))


def _assigned_spiderfarmer_ppfd(runtime):
    """Return PPFD from this station's assigned Spider Farmer environment source.

    PPFD.1 deliberately reuses the existing temperature/humidity sensor
    assignment as the station binding. No control logic is changed.
    """

    assignments = runtime.config.get("SENSOR_ASSIGNMENTS", {})
    if not isinstance(assignments, dict):
        return None, None

    source_ids = []

    # PPFD.2: explicit station assignment has priority.
    ppfd_assignment = assignments.get("ppfd") or {}
    ppfd_source_id = str(ppfd_assignment.get("source_id") or "").strip()
    if ppfd_source_id:
        source_ids.append(ppfd_source_id)

    # Migration fallback for stations configured before PPFD.2.
    for sensor_name in ("temperature", "humidity"):
        assignment = assignments.get(sensor_name) or {}
        source_id = str(assignment.get("source_id") or "").strip()
        if source_id.startswith("spiderfarmer:") and source_id not in source_ids:
            source_ids.append(source_id)

    for source_id in source_ids:
        source = get_sensor_source(source_id)
        if not isinstance(source, dict):
            continue

        value = source.get("ppfd")
        if value is None:
            continue

        try:
            ppfd = float(value)
        except (TypeError, ValueError):
            continue

        return ppfd, {
            "source_id": source_id,
            "label": source.get("label") or source_id,
            "last_seen": source.get("last_seen"),
        }

    return None, None


def _controller_readback(runtime, device):
    """Read-only projection of the assigned Spider Farmer controller values."""
    assignment = controller_assignment_for_config(runtime.config, device)
    if not isinstance(assignment, dict):
        return None

    if str(assignment.get("provider") or "") != "spiderfarmer":
        return None

    controller_id = str(assignment.get("controller_id") or "").strip().lower()
    device_id = str(assignment.get("device_id") or "").strip()

    if not controller_id or not device_id:
        target_id = str(assignment.get("target_id") or "").strip()
        prefix = "spiderfarmer:"
        if not target_id.startswith(prefix):
            return None
        controller_id, separator, device_id = target_id[len(prefix):].partition(":")
        controller_id = controller_id.strip().lower()
        device_id = device_id.strip()
        if not separator or not controller_id or not device_id:
            return None

    observed = spiderfarmer_device(controller_id, device_id)
    if not isinstance(observed, dict):
        return None

    effective = observed.get("effective")
    if not isinstance(effective, dict):
        return None

    result = {
        "provider": "spiderfarmer",
        "controller_id": controller_id,
        "device_id": device_id,
    }

    for field in ("on", "level", "oscillation_level", "mode_type"):
        if field in effective:
            result[field] = effective[field]

    # GGS getDevSta liefert für den Ventilator den Live-Level, aber keinen
    # aktuellen shakeLevel/Oszillations-Istwert. Ein älterer setConfigField-
    # Block im kanonischen Read-Model darf deshalb nicht als Live-Oszillation
    # ausgegeben werden. Für die Dashboard-Anzeige verwenden wir bei fan
    # stattdessen den stationsbezogen persistierten Controller-Setpoint.
    if device_id == "fan":
        params = (runtime.config.get("DEVICE_PARAMS") or {}).get(device) or {}

        # Prefer the exact controller values that the live runtime has already
        # applied successfully. This is the closest available truth because
        # GGS getDevSta does not expose shakeLevel.
        with runtime.state_lock:
            applied_map = runtime.state.live_state.get("_controller_applied")
            applied = (
                dict(applied_map.get(device) or {})
                if isinstance(applied_map, dict)
                else {}
            )

        if "oscillation" in applied:
            result["oscillation_level"] = applied["oscillation"]
            result["oscillation_source"] = "applied_controller_state"
        else:
            # After a process restart the applied cache can be empty before the
            # first control pass. Fall back to the currently selected Growstar
            # operating state's own controller values, not to the legacy
            # params["controller"] default.
            mode_name = str(get_device_mode(device, runtime=runtime) or "").upper()
            state_name = {
                "ON": "on",
                "TIME": "time",
                "ENV": "env",
            }.get(mode_name)

            configured = {}
            if state_name:
                configured = (
                    resolve_control_state(params, state_name).get("controller")
                    or {}
                )

            if "oscillation" in configured:
                result["oscillation_level"] = configured["oscillation"]
                result["oscillation_source"] = "active_mode_setpoint"
            else:
                result.pop("oscillation_level", None)

    return result if len(result) > 3 else None


def _state_snapshot(runtime):
    st = runtime.state
    cfg = runtime.config

    with runtime.state_lock:
        live = dict(st.live_state)
        shadow_outputs = dict(runtime.shadow_outputs)

    safety = get_runtime_safety_snapshot(runtime)

    light_ppfd = live.get("light_ppfd")
    light_ppfd_source = live.get("light_ppfd_source")
    if light_ppfd is None:
        light_ppfd, light_ppfd_source = _assigned_spiderfarmer_ppfd(runtime)

    devices = {}
    for device in _DEVICE_NAMES:
        assignment = device_assignment(runtime.tent_id, device)
        health = None
        if assignment.get("configured"):
            health = get_endpoint_health(assignment["ip"], assignment["relay"])

        runtime_on = bool(getattr(st, f"{device}_on", False))
        physical_known = bool(
            health
            and health.get("state") == "ok"
            and isinstance(health.get("actual_state"), bool)
        )
        safety_override = dict((safety.get("overrides") or {}).get(device) or {})

        devices[device] = {
            "actual_on": runtime_on,
            "runtime_on": runtime_on,
            "mode": get_device_mode(device, runtime=runtime),
            "shadow_desired": shadow_outputs.get(device),
            "assigned": bool(assignment.get("configured")),
            "assignment": assignment,
            "hardware_health": health,
            "physical_known": physical_known,
            "physical_on": health.get("actual_state") if physical_known else None,
            "safety_blocked": device in (safety.get("blocked_devices") or []),
            "safety_force_off": bool(safety_override.get("force_off")),
            "safety_block_on": bool(safety_override.get("block_on")),
            "safety_reason": safety_override.get("reason"),
            "controller_readback": _controller_readback(runtime, device),
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
        "live_requested": bool(getattr(runtime, "live_requested", False)),
        "arming": bool(getattr(runtime, "arming", False)),
        "hardware_actuation_blocked": not runtime.control_enabled,

        # Sensoren / Sollwerte
        "temp_raw": live.get("temp_raw"),
        "temp": live.get("temp"),
        "hum_raw": live.get("hum_raw"),
        "hum": live.get("hum"),
        "vpd": live.get("vpd"),
        "light_ppfd": light_ppfd,
        "light_ppfd_source": light_ppfd_source,
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

        # Licht · Sonnenverlauf
        "light_sun_enabled": bool(cfg.get("LIGHT_SUN_ENABLED", 0)),
        "light_sun_active": bool(live.get("light_sun_active")),
        "light_sun_phase": live.get("light_sun_phase"),
        "light_sun_level": live.get("light_sun_level"),
        "light_sun_progress": live.get("light_sun_progress"),

        # Sensorzustand
        "temp_ok": not st.temp_stale,
        "hum_ok": not st.hum_stale,
        "temp_age": _age(st.last_ds_time),
        "hum_age": _age(st.last_dht_time),

        # Reale vs. nur berechnete Ausgänge
        "devices": devices,
        "shadow_outputs": shadow_outputs,
        "device_modes": cfg.get("DEVICE_MODES", {}),

        "safety": {
            "active": bool(safety.get("active")),
            "stale": bool(safety.get("stale")),
            "state": safety.get("state"),
            "reason": safety.get("reason"),
            "blocked_devices": list(safety.get("blocked_devices") or []),
            "age": safety.get("age"),
        },

        # Energie bleibt vorerst Runtime-lokal/leer für zusätzliche Stationen.
        "energy": dict(runtime.energy_state),
    }


def _light_sun_availability(runtime):
    assignment = controller_assignment_for_config(runtime.config, "light")

    if not isinstance(assignment, dict):
        return {
            "available": False,
            "reason": (
                "Sonnenaufgang/Sonnenuntergang benötigt einen zugewiesenen "
                "Licht-Controller mit Dimmfunktion. Bitte unter Grow Control "
                "→ Controller-Funktionen zuerst einen Controller für "
                "Beleuchtung zuweisen."
            ),
            "assignment": None,
        }

    target_id = str(assignment.get("target_id") or "").strip()
    provider = str(assignment.get("provider") or "").strip()

    if not target_id:
        return {
            "available": False,
            "reason": (
                "Die Beleuchtung besitzt keine vollständige "
                "Controller-Zuweisung. Bitte die Controller-Zuordnung "
                "erneut speichern."
            ),
            "assignment": None,
        }

    return {
        "available": True,
        "reason": None,
        "assignment": {
            "provider": provider,
            "target_id": target_id,
        },
    }


def _config_payload(runtime):
    sun = _light_sun_availability(runtime)

    return {
        "success": True,
        "tent_id": runtime.tent_id,
        "name": runtime.name,
        "control_enabled": runtime.control_enabled,
        "shadow_enabled": runtime.shadow_enabled,
        "live_requested": bool(getattr(runtime, "live_requested", False)),
        "arming": bool(getattr(runtime, "arming", False)),
        "hardware_actuation_blocked": not runtime.control_enabled,
        "active_profile": get_active_profile(runtime=runtime),
        "profiles": sorted((PROFILES.get("profiles") or {}).keys()),
        "light_sun_available": bool(sun["available"]),
        "light_sun_unavailable_reason": sun["reason"],
        "light_sun_controller_assignment": sun["assignment"],
        "config": config_snapshot(runtime),
    }


def _profiles_payload(runtime):
    sun = _light_sun_availability(runtime)

    return {
        "success": True,
        "tent_id": runtime.tent_id,
        "active_profile": get_active_profile(runtime=runtime),
        "profiles": profile_catalog(),
        "current_settings": profile_settings_from_config(runtime.config),
        "profile_setting_keys": list(PROFILE_SETTING_KEYS),
        "catalog_scope": "controller",
        "current_settings_scope": "station",
        "light_sun_available": bool(sun["available"]),
        "light_sun_unavailable_reason": sun["reason"],
    }


def _tent_list_payload():
    runtimes = _runtime_map()
    result = []

    for tent in tent_manager.list_tents():
        runtime = runtimes.get(tent["id"])
        item = dict(tent)

        # Konfigurierter Zustand und tatsächlich laufender Zustand werden
        # getrennt ausgegeben. Änderungen an enabled/shadow greifen bewusst
        # erst nach einem Backend-Neustart und dürfen den Hub vorher nicht
        # fälschlich als bereits aktiv darstellen.
        item["configured_enabled"] = bool(tent.get("enabled", True))
        item["configured_shadow_enabled"] = bool(tent.get("shadow_enabled", False))
        item["configured_control_enabled"] = bool(tent.get("control_enabled", False))
        item.update({
            "runtime_loaded": runtime is not None,
            "runtime_mode": runtime.loop_mode if runtime else "unloaded",
            "last_loop_ts": runtime.last_loop_ts if runtime else None,
            "enabled": bool(runtime.enabled) if runtime else bool(tent.get("enabled", True)),
            "shadow_enabled": bool(runtime.shadow_enabled) if runtime else False,
            "control_enabled": bool(runtime.control_enabled) if runtime else False,
            "live_requested": bool(getattr(runtime, "live_requested", False)) if runtime else bool(tent.get("control_enabled", False)),
            "arming": bool(getattr(runtime, "arming", False)) if runtime else False,
            "hardware_actuation_blocked": (
                not runtime.control_enabled if runtime else True
            ),
        })

        if runtime is not None:
            item["name"] = runtime.name
            with runtime.state_lock:
                item["temp"] = runtime.state.live_state.get("temp")
                item["hum"] = runtime.state.live_state.get("hum")
                item["vpd"] = runtime.state.live_state.get("vpd")

        result.append(item)

    return {
        "success": True,
        "default_tent_id": tent_manager.default_tent_id(),
        "tents": result,
    }


def register(app):
    """Generische Multi-Station-API für beliebig viele lokale Runtimes."""

    @app.route("/api/tents", methods=["GET", "POST"])
    def api_tents():
        if request.method == "GET":
            return jsonify(_tent_list_payload())

        data = request.get_json(silent=True) or {}
        try:
            tent_id = validate_tent_id(data.get("tent_id", ""))
            item = tent_manager.add_tent(
                tent_id,
                name=data.get("name") or tent_id,
                enabled=bool(data.get("enabled", True)),
                shadow_enabled=bool(data.get("shadow_enabled", False)),
                control_enabled=False,
            )
            ensure_tent_config(tent_id)
        except (TypeError, ValueError) as exc:
            return jsonify(success=False, error=str(exc)), 400

        return jsonify({
            "success": True,
            "tent": item,
            "restart_required": True,
            "message": "Station angelegt. Backend-Neustart erforderlich, damit die Runtime geladen wird.",
        }), 201

    @app.route("/api/tents/<tent_id>", methods=["GET", "PATCH"])
    def api_tent_meta(tent_id):
        tent, error = _find_tent(tent_id)
        if error:
            return error

        if request.method == "GET":
            return jsonify(success=True, tent=tent)

        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify(success=False, error="invalid_payload"), 400

        allowed = {"name", "enabled", "shadow_enabled"}
        unknown = sorted(set(data) - allowed)
        if unknown:
            return jsonify(
                success=False,
                error="Unbekannte Stationsfelder: " + ", ".join(unknown),
            ), 400

        restart_required = "enabled" in data or "shadow_enabled" in data
        try:
            tent = tent_manager.update_tent(
                tent_id,
                name=data.get("name") if "name" in data else None,
                enabled=data.get("enabled") if "enabled" in data else None,
                shadow_enabled=(
                    data.get("shadow_enabled")
                    if "shadow_enabled" in data
                    else None
                ),
            )

            # Eine reine Umbenennung kann sofort in die geladene Runtime
            # gespiegelt werden. enabled/shadow bleiben bis zum Neustart
            # bewusst nur konfigurierte Metadaten.
            if "name" in data:
                try:
                    get_runtime(tent_id).name = tent["name"]
                except KeyError:
                    pass

        except KeyError:
            return jsonify(success=False, error="tent_not_found"), 404
        except ValueError as exc:
            return jsonify(success=False, error=str(exc)), 400

        return jsonify({
            "success": True,
            "tent": tent,
            "restart_required": restart_required,
        })

    @app.route("/api/tents/<tent_id>/state", methods=["GET"])
    def api_tent_state(tent_id):
        runtime, error = _find_runtime(tent_id)
        if error:
            return error
        return jsonify(_state_snapshot(runtime))

    @app.route("/api/tents/<tent_id>/live-preflight", methods=["GET"])
    def api_tent_live_preflight(tent_id):
        runtime, error = _find_runtime(tent_id)
        if error:
            return error
        return jsonify(evaluate_live_preflight(runtime))

    @app.route("/api/tents/<tent_id>/live", methods=["POST"])
    def api_tent_live_transition(tent_id):
        runtime, error = _find_runtime(tent_id)
        if error:
            return error

        data = request.get_json(silent=True) or {}
        enabled = data.get("enabled")
        if not isinstance(enabled, bool):
            return jsonify(
                success=False,
                error="invalid_payload",
                message="enabled muss true oder false sein",
            ), 400

        try:
            result = request_live(runtime.tent_id) if enabled else request_shadow(runtime.tent_id)
        except LiveTransitionError as exc:
            return jsonify(
                success=False,
                error=exc.code,
                message=str(exc),
                preflight=exc.preflight,
            ), 409
        except (KeyError, ValueError) as exc:
            return jsonify(success=False, error=str(exc)), 400

        payload = dict(result)
        payload["state"] = _state_snapshot(get_runtime(runtime.tent_id))
        payload["tent"] = tent_manager.get(runtime.tent_id)
        return jsonify(payload)

    @app.route("/api/tents/<tent_id>/config", methods=["GET", "POST"])
    def api_tent_config(tent_id):
        runtime, error = _find_runtime(tent_id)
        if error:
            return error

        if request.method == "GET":
            return jsonify(_config_payload(runtime))

        data = request.get_json(silent=True) or {}

        if bool(data.get("LIGHT_SUN_ENABLED")):
            sun = _light_sun_availability(runtime)
            if not sun["available"]:
                return jsonify(
                    success=False,
                    error="light_sun_controller_required",
                    message=sun["reason"],
                ), 409

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

        try:
            applied = apply_profile(name, runtime=runtime)
        except ProfileActivationError as exc:
            return jsonify(
                success=False,
                error=exc.code,
                message=str(exc),
                profile=name,
            ), 409

        if not applied:
            return jsonify(
                success=False,
                error="profile_not_found",
                profile=name,
            ), 404

        return jsonify(_config_payload(runtime))

    @app.get("/api/tents/<tent_id>/profiles")
    def api_tent_profiles(tent_id):
        runtime, error = _find_runtime(tent_id)
        if error:
            return error

        return jsonify(_profiles_payload(runtime))

    @app.put("/api/tents/<tent_id>/profiles/<name>")
    def api_tent_profile_update(tent_id, name):
        runtime, error = _find_runtime(tent_id)
        if error:
            return error

        data = request.get_json(silent=True)

        try:
            saved = update_profile(name, data)
        except KeyError:
            return jsonify(
                success=False,
                error="profile_not_found",
                profile=name,
            ), 404
        except (TypeError, ValueError) as exc:
            return jsonify(success=False, error=str(exc)), 400
        except OSError:
            return jsonify(
                success=False,
                error="profile_save_failed",
                message="Profil konnte nicht dauerhaft gespeichert werden.",
            ), 500

        payload = _profiles_payload(runtime)
        payload.update({
            "saved_profile": name,
            "saved_settings": saved,
            "runtime_config_changed": False,
        })
        return jsonify(payload)

    @app.route("/api/tents/<tent_id>/hardware", methods=["GET", "POST"])
    def api_tent_hardware(tent_id):
        tent, error = _find_tent(tent_id)
        if error:
            return error

        if request.method == "GET":
            try:
                return jsonify(hardware_snapshot(tent_id))
            except (KeyError, ValueError) as exc:
                return jsonify(success=False, error=str(exc)), 400

        data = request.get_json(silent=True) or {}
        try:
            return jsonify(update_hardware_assignments(tent_id, data))
        except PermissionError as exc:
            return jsonify(
                success=False,
                error="live_hardware_edit_blocked",
                message=str(exc),
            ), 409
        except HardwareAssignmentActiveModeError as exc:
            return jsonify(
                success=False,
                error="hardware_assignment_active_mode",
                message=str(exc),
                device=exc.device,
                mode=exc.mode,
                current=exc.current,
                requested=exc.requested,
            ), 409
        except HardwareAssignmentNotSafeOffError as exc:
            return jsonify(
                success=False,
                error="hardware_assignment_not_safe_off",
                message=str(exc),
                device=exc.device,
                current=exc.current,
                health=exc.health,
            ), 409
        except HardwareConflictError as exc:
            return jsonify(
                success=False,
                error="hardware_endpoint_conflict",
                message=str(exc),
                endpoint=exc.endpoint,
                owner=exc.owner,
                contender=exc.contender,
            ), 409
        except (TypeError, ValueError) as exc:
            return jsonify(success=False, error=str(exc)), 400
