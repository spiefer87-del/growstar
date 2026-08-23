"""Controller-aware device operating states.

CTRL.1 adds a provider-neutral state layer between the existing regulation
modes and the physical/controller actuators.

Safety invariant:
    Shelly power is authoritative.

A state with power=False NEVER sends controller setpoints.  The physical
Shelly actuator is switched off and any cached controller command is forgotten.
Controller values can only be sent for a requested ON state after the existing
Shelly path has accepted that state in the live runtime.

Existing installations remain compatible:
    params["controller"]               -> default ON controller state
    INTERVAL without control_states    -> phase A ON / phase B OFF

Optional future shape:
    params["control_states"] = {
        "on": {
            "power": True,
            "controller": {"level": 7},
        },
        "interval_a": {
            "power": True,
            "controller": {"level": 7},
        },
        "interval_b": {
            "power": True,
            "controller": {"level": 3},
        },
    }
"""

from __future__ import annotations

from copy import deepcopy

from core.actuators import set_device
from core.capability_routing import (
    controller_assignment_for_config,
    spiderfarmer_control_targets,
)
from core.controller_setpoints import (
    controller_schema,
    normalize_controller_setpoints,
)
from core.runtime import resolve_runtime
from services.spiderfarmer_commands import send_controller_setpoints


CONTROL_STATES_KEY = "control_states"


def _mapping(value):
    return deepcopy(value) if isinstance(value, dict) else {}


def _base_controller(params):
    params = params if isinstance(params, dict) else {}
    return _mapping(params.get("controller"))


def _raw_control_state(params, name):
    params = params if isinstance(params, dict) else {}
    states = params.get(CONTROL_STATES_KEY)
    if not isinstance(states, dict):
        return {}
    return _mapping(states.get(name))


def resolve_control_state(params, name):
    """Resolve one logical operating state with backward-compatible defaults."""

    name = str(name or "").strip().lower()
    params = params if isinstance(params, dict) else {}
    base = _base_controller(params)
    raw = _raw_control_state(params, name)

    if name == "off":
        # Hard invariant: controller values never belong to an OFF state.
        return {
            "power": False,
            "controller": {},
        }

    if name == "on":
        return {
            "power": bool(raw.get("power", True)),
            "controller": _mapping(raw.get("controller")) or base,
        }

    if name == "interval_a":
        return {
            "power": bool(raw.get("power", True)),
            "controller": _mapping(raw.get("controller")) or base,
        }

    if name == "interval_b":
        # Historical Growstar interval semantics were ON then OFF.
        # Therefore B remains power-off unless explicitly configured otherwise.
        power = bool(raw.get("power", False))
        return {
            "power": power,
            "controller": (
                _mapping(raw.get("controller"))
                if power
                else {}
            ),
        }

    raise ValueError(f"Unbekannter Regelzustand: {name}")


def _controller_cache(runtime):
    state = runtime.state
    with runtime.state_lock:
        cache = state.live_state.get("_controller_applied")
        if not isinstance(cache, dict):
            cache = {}
            state.live_state["_controller_applied"] = cache
        return cache


def _clear_controller_cache(runtime, device):
    with runtime.state_lock:
        cache = runtime.state.live_state.get("_controller_applied")
        if isinstance(cache, dict):
            cache.pop(device, None)


def _target_for_device(runtime, device):
    assignment = controller_assignment_for_config(
        runtime.config,
        device,
    )
    if not isinstance(assignment, dict):
        return None

    target_id = str(assignment.get("target_id") or "").strip()
    provider = str(assignment.get("provider") or "").strip()

    if not target_id or provider != "spiderfarmer":
        return None

    for target in spiderfarmer_control_targets():
        if str(target.get("id") or "") == target_id:
            return target

    return None


def _apply_controller(runtime, device, setpoints):
    requested = _mapping(setpoints)
    if not requested:
        return {
            "success": True,
            "status": "no_controller_values",
        }

    cache = _controller_cache(runtime)
    if cache.get(device) == requested:
        return {
            "success": True,
            "status": "unchanged",
        }

    target = _target_for_device(runtime, device)
    if not isinstance(target, dict):
        return {
            "success": False,
            "status": "controller_not_available",
        }

    schema = controller_schema(target)
    try:
        normalized = normalize_controller_setpoints(
            requested,
            schema,
        )
    except (TypeError, ValueError) as exc:
        return {
            "success": False,
            "status": "invalid_controller_state",
            "message": str(exc),
        }

    response = send_controller_setpoints(
        controller_id=target.get("controller_id"),
        pid=target.get("controller_pid"),
        module=target.get("device_id"),
        setpoints=normalized,
    )

    if isinstance(response, dict) and response.get("success"):
        with runtime.state_lock:
            cache = runtime.state.live_state.setdefault(
                "_controller_applied",
                {},
            )
            cache[device] = deepcopy(normalized)

    return response


def apply_device_state(
    device,
    state,
    *,
    runtime=None,
    reason="",
):
    """Apply power + controller state while keeping Shelly authoritative.

    OFF:
        Shelly OFF is requested.
        No controller command is ever sent.

    ON:
        Shelly ON is requested through the existing Safety/Shadow path.
        Controller values are sent only if the live runtime reports that this
        device is actually in its logical ON state afterwards.

    This function intentionally does not bypass any existing Shelly safety
    barrier in core.actuators.
    """

    rt = resolve_runtime(runtime)
    state = state if isinstance(state, dict) else {}

    power = bool(state.get("power"))
    controller_values = _mapping(state.get("controller"))

    if not power:
        # Shelly has absolute authority over physical OFF.
        set_device(
            device,
            False,
            runtime=rt,
            reason=reason,
        )
        _clear_controller_cache(rt, device)
        return {
            "power": False,
            "controller": {
                "success": True,
                "status": "skipped_power_off",
            },
        }

    set_device(
        device,
        True,
        runtime=rt,
        reason=reason,
    )

    # Never allow a controller command to bypass Shadow/Safety or a failed
    # Shelly ON. The existing runtime state is the gate.
    if not bool(getattr(rt.state, f"{device}_on", False)):
        return {
            "power": False,
            "controller": {
                "success": False,
                "status": "blocked_by_power_path",
            },
        }

    try:
        controller_result = _apply_controller(
            rt,
            device,
            controller_values,
        )
    except Exception as exc:
        controller_result = {
            "success": False,
            "status": "controller_error",
            "message": str(exc),
        }

    return {
        "power": True,
        "controller": controller_result,
    }
