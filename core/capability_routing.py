"""Capability-based hardware routing for Growstar SF.4A.

SF.4A introduces the assignment model only. It does not send commands.

A logical Growstar device can have different physical providers for different
capabilities:

    power       -> existing Shelly relay (current source of truth)
    level       -> optional controller target, e.g. Spider Farmer GGS
    oscillation -> optional controller target, e.g. Spider Farmer GGS fan

The model is provider-neutral. Spider Farmer is merely the first modulation
provider. Future providers can expose the same capabilities without changing
the Growstar control loop.

Spider Farmer outlet channels are already represented as future ``power``
targets, but SF.4A deliberately keeps them non-assignable until their real
actuation path is implemented and verified.
"""

from __future__ import annotations

from copy import deepcopy

from core.config import config as default_config, save_config
from core.devices import DEVICE_META, DEVICE_NAMES, validate_device_name
from core.hardware_assignments import DEVICE_HARDWARE
from core.runtime import get_runtime, list_runtimes
from core.tent_config import ensure_tent_config, load_tent_config, save_tent_config
from core.tents import DEFAULT_TENT_ID, manager as tent_manager, validate_tent_id


CONFIG_KEY = "CAPABILITY_ROUTES"

CAPABILITY_POWER = "power"
CAPABILITY_LEVEL = "level"
CAPABILITY_OSCILLATION = "oscillation"

# Capabilities are properties of the logical Growstar device, not of a
# particular hardware vendor. This makes a future controller interchangeable
# as long as it exposes the required capability.
DEVICE_CAPABILITIES = {
    "heating": (CAPABILITY_POWER,),
    "fan": (CAPABILITY_POWER, CAPABILITY_LEVEL),
    "light": (CAPABILITY_POWER, CAPABILITY_LEVEL),
    "vent": (CAPABILITY_POWER, CAPABILITY_LEVEL, CAPABILITY_OSCILLATION),
    "irrigation": (CAPABILITY_POWER,),
    "humidifier": (CAPABILITY_POWER,),
    "dehumidifier": (CAPABILITY_POWER,),
    "light2": (CAPABILITY_POWER, CAPABILITY_LEVEL),
    "vent2": (CAPABILITY_POWER, CAPABILITY_LEVEL, CAPABILITY_OSCILLATION),
    "aux1": (CAPABILITY_POWER,),
    "aux2": (CAPABILITY_POWER,),
    "aux3": (CAPABILITY_POWER,),
    "aux4": (CAPABILITY_POWER,),
}

EDITABLE_CAPABILITIES = {
    CAPABILITY_LEVEL,
    CAPABILITY_OSCILLATION,
}


class CapabilityRouteConflictError(ValueError):
    def __init__(self, capability, target_id, *, owner=None, contender=None):
        self.capability = str(capability)
        self.target_id = str(target_id)
        self.owner = deepcopy(owner)
        self.contender = deepcopy(contender)

        super().__init__(
            f"{self.capability}: Steuerziel {self.target_id} ist bereits "
            "einem anderen Growstar-Gerät zugeordnet."
        )


def _runtime_map():
    return {runtime.tent_id: runtime for runtime in list_runtimes()}


def _registered_config(tent_id, runtime_map=None):
    tent_id = validate_tent_id(tent_id)
    runtime_map = runtime_map or _runtime_map()

    runtime = runtime_map.get(tent_id)
    if runtime is not None:
        return runtime.config, runtime

    if tent_id == DEFAULT_TENT_ID:
        return default_config, None

    ensure_tent_config(tent_id)
    return load_tent_config(tent_id), None


def _save_registered_config(tent_id, cfg, runtime=None):
    tent_id = validate_tent_id(tent_id)

    if runtime is not None:
        runtime.config.clear()
        runtime.config.update(cfg)
        runtime.persist_config()
        return

    if tent_id == DEFAULT_TENT_ID:
        default_config.clear()
        default_config.update(cfg)
        save_config(default_config)
        return

    save_tent_config(tent_id, cfg)


def _target_id(controller_id, device_id):
    return (
        "spiderfarmer:"
        f"{str(controller_id or '').strip().lower()}:"
        f"{str(device_id or '').strip()}"
    )


def spiderfarmer_control_targets(controllers=None):
    """Project normalized Spider Farmer devices into generic control targets.

    This is inventory only. ``writable`` remains False throughout SF.4A.
    ``assignment_enabled`` means that a route may already be configured, not
    that Growstar is allowed to send a hardware command yet.
    """

    if controllers is None:
        from services.spiderfarmer import list_controllers
        controllers = list_controllers()

    result = []

    for controller in controllers or []:
        if not isinstance(controller, dict):
            continue

        controller_id = str(controller.get("id") or "").strip().lower()
        if not controller_id:
            continue

        pid = controller.get("pid")
        online = bool(controller.get("online"))

        for device in controller.get("devices") or []:
            if not isinstance(device, dict):
                continue

            device_id = str(device.get("id") or "").strip()
            capabilities = set(device.get("capabilities") or [])

            modulation = []

            if "level" in capabilities and device_id in (
                "light",
                "light2",
                "fan",
                "blower",
            ):
                modulation.append(CAPABILITY_LEVEL)

            if (
                "oscillation_level" in capabilities
                and device_id == "fan"
            ):
                modulation.append(CAPABILITY_OSCILLATION)

            if modulation:
                result.append({
                    "id": _target_id(controller_id, device_id),
                    "provider": "spiderfarmer",
                    "controller_id": controller_id,
                    "controller_pid": pid,
                    "device_id": device_id,
                    "label": (
                        f"{device.get('label') or device_id} · "
                        f"GGS {controller_id[-4:].upper()}"
                    ),
                    "capabilities": sorted(set(modulation)),
                    "online": online,
                    "writable": False,
                    "assignment_enabled": True,
                    "role": "modulation_controller",
                })

            # Future power actors: Spider Farmer outlet channels are already
            # discoverable in the routing inventory but cannot yet replace
            # Shelly. That switch belongs to a later, separately verified phase.
            for channel in device.get("channels") or []:
                if not isinstance(channel, dict):
                    continue
                channel_caps = set(channel.get("capabilities") or [])
                channel_id = str(channel.get("id") or "").strip()

                if "power" not in channel_caps or not channel_id:
                    continue

                result.append({
                    "id": _target_id(controller_id, channel_id),
                    "provider": "spiderfarmer",
                    "controller_id": controller_id,
                    "controller_pid": pid,
                    "device_id": channel_id,
                    "label": (
                        f"Steckdose {channel.get('label') or channel_id} · "
                        f"GGS {controller_id[-4:].upper()}"
                    ),
                    "capabilities": [CAPABILITY_POWER],
                    "online": online,
                    "writable": False,
                    "assignment_enabled": False,
                    "role": "future_power_actor",
                })

    result.sort(
        key=lambda item: (
            str(item.get("provider") or ""),
            str(item.get("controller_id") or ""),
            str(item.get("device_id") or ""),
        )
    )

    return result


def control_target_inventory(controllers=None):
    targets = spiderfarmer_control_targets(controllers)

    return {
        "success": True,
        "phase": "SF.4A",
        "read_only": True,
        "command_transport_enabled": False,
        "targets": targets,
    }


def _target_map(targets):
    return {
        str(item.get("id") or ""): item
        for item in targets or []
        if isinstance(item, dict) and item.get("id")
    }


def _logical_capabilities(device):
    validate_device_name(device)
    return tuple(DEVICE_CAPABILITIES.get(device) or (CAPABILITY_POWER,))


def _normalize_assignment(device, capability, raw, target_map):
    validate_device_name(device)

    capability = str(capability or "").strip().lower()

    if capability not in _logical_capabilities(device):
        raise ValueError(
            f"{device}: Capability {capability!r} wird vom logischen "
            "Growstar-Gerät nicht unterstützt."
        )

    if capability not in EDITABLE_CAPABILITIES:
        raise ValueError(
            f"{device}: Capability {capability!r} bleibt in SF.4A "
            "noch am bestehenden Power-Aktor gebunden."
        )

    if raw in (None, "", False):
        return None

    if not isinstance(raw, dict):
        raise TypeError(
            f"{device}/{capability}: Zuordnung muss ein JSON-Objekt sein."
        )

    target_id = str(
        raw.get("target_id")
        or raw.get("target")
        or ""
    ).strip()

    if not target_id:
        return None

    target = target_map.get(target_id)
    if target is None:
        raise ValueError(
            f"{device}/{capability}: unbekanntes Steuerziel {target_id!r}"
        )

    if not target.get("assignment_enabled"):
        raise ValueError(
            f"{device}/{capability}: Steuerziel {target_id!r} ist "
            "in dieser Phase noch nicht zuweisbar."
        )

    if capability not in (target.get("capabilities") or []):
        raise ValueError(
            f"{device}/{capability}: Steuerziel {target_id!r} unterstützt "
            "diese Capability nicht."
        )

    return {
        "provider": str(target.get("provider") or ""),
        "target_id": target_id,
    }


def normalize_route_patch(data, targets):
    """Normalize an SF.4A routing update without writing configuration."""

    if not isinstance(data, dict):
        raise TypeError("Capability-Routing-Update muss ein JSON-Objekt sein.")

    raw_routes = data.get("routes", data)
    if not isinstance(raw_routes, dict):
        raise TypeError("routes muss ein JSON-Objekt sein.")

    unknown_devices = sorted(set(raw_routes) - set(DEVICE_NAMES))
    if unknown_devices:
        raise ValueError(
            "Unbekannte Growstar-Geräte: " + ", ".join(unknown_devices)
        )

    target_map = _target_map(targets)
    normalized = {}

    for device, raw_device in raw_routes.items():
        if not isinstance(raw_device, dict):
            raise TypeError(
                f"{device}: Capability-Zuordnungen müssen ein JSON-Objekt sein."
            )

        normalized[device] = {}

        for capability, raw_assignment in raw_device.items():
            normalized[device][capability] = _normalize_assignment(
                device,
                capability,
                raw_assignment,
                target_map,
            )

    _assert_local_route_uniqueness(normalized)

    return normalized


def _assert_local_route_uniqueness(routes):
    owners = {}

    for device, capability_routes in routes.items():
        for capability, assignment in capability_routes.items():
            if not assignment:
                continue

            key = (capability, assignment["target_id"])
            owner = owners.get(key)
            contender = {
                "device": device,
                "capability": capability,
            }

            if owner is not None and owner != contender:
                raise CapabilityRouteConflictError(
                    capability,
                    assignment["target_id"],
                    owner=owner,
                    contender=contender,
                )

            owners[key] = contender


def _stored_routes(cfg):
    routes = cfg.get(CONFIG_KEY) if isinstance(cfg, dict) else None
    return deepcopy(routes) if isinstance(routes, dict) else {}


def _apply_normalized_patch(cfg, normalized):
    routes = _stored_routes(cfg)

    for device, capability_routes in normalized.items():
        current = routes.get(device)
        if not isinstance(current, dict):
            current = {}

        for capability, assignment in capability_routes.items():
            if assignment is None:
                current.pop(capability, None)
            else:
                current[capability] = deepcopy(assignment)

        if current:
            routes[device] = current
        else:
            routes.pop(device, None)

    cfg[CONFIG_KEY] = routes
    return routes


def _assert_global_route_uniqueness(
    tent_id,
    candidate_routes,
    *,
    runtime_map=None,
):
    runtime_map = runtime_map or _runtime_map()
    owners = {}

    for tent in tent_manager.list_tents():
        other_tent_id = tent.get("id")
        if not other_tent_id:
            continue

        if other_tent_id == tent_id:
            routes = candidate_routes
        else:
            cfg, _ = _registered_config(other_tent_id, runtime_map)
            routes = _stored_routes(cfg)

        for device, capability_routes in routes.items():
            if not isinstance(capability_routes, dict):
                continue

            for capability, assignment in capability_routes.items():
                if not isinstance(assignment, dict):
                    continue

                target_id = str(assignment.get("target_id") or "").strip()
                if not target_id:
                    continue

                key = (str(capability), target_id)
                current = {
                    "tent_id": other_tent_id,
                    "device": device,
                    "capability": capability,
                }

                owner = owners.get(key)
                if owner is not None and owner != current:
                    raise CapabilityRouteConflictError(
                        capability,
                        target_id,
                        owner=owner,
                        contender=current,
                    )

                owners[key] = current


def _legacy_power_route(cfg, device):
    meta = DEVICE_HARDWARE.get(device) or {}
    host = str(cfg.get(meta.get("ip_key")) or "").strip()
    relay = cfg.get(meta.get("relay_key"))

    try:
        relay = int(relay) if relay not in (None, "") else None
    except (TypeError, ValueError):
        relay = None

    if not host or relay is None:
        return {
            "capability": CAPABILITY_POWER,
            "provider": "shelly",
            "target_id": None,
            "configured": False,
            "editable_here": False,
            "source": "legacy_shelly_assignment",
        }

    return {
        "capability": CAPABILITY_POWER,
        "provider": "shelly",
        "target_id": f"shelly:{host.lower()}:relay:{relay}",
        "configured": True,
        "editable_here": False,
        "source": "legacy_shelly_assignment",
        "host": host,
        "relay": relay,
    }


def routing_snapshot_for_config(cfg, *, targets=None):
    targets = (
        spiderfarmer_control_targets()
        if targets is None
        else list(targets)
    )
    stored = _stored_routes(cfg)

    devices = {}

    for device in DEVICE_NAMES:
        meta = DEVICE_META.get(device) or {}
        routes = {
            CAPABILITY_POWER: _legacy_power_route(cfg, device),
        }

        current = stored.get(device)
        if not isinstance(current, dict):
            current = {}

        for capability in _logical_capabilities(device):
            if capability == CAPABILITY_POWER:
                continue

            assignment = current.get(capability)
            if not isinstance(assignment, dict):
                assignment = None

            routes[capability] = {
                "capability": capability,
                "configured": bool(assignment),
                "editable_here": capability in EDITABLE_CAPABILITIES,
                "provider": (
                    assignment.get("provider")
                    if assignment
                    else None
                ),
                "target_id": (
                    assignment.get("target_id")
                    if assignment
                    else None
                ),
            }

        devices[device] = {
            "device": device,
            "label": meta.get("label") or device,
            "icon": meta.get("icon") or "🔌",
            "capabilities": list(_logical_capabilities(device)),
            "routes": routes,
        }

    return {
        "phase": "SF.4A",
        "read_only_control_plane": True,
        "command_transport_enabled": False,
        "devices": devices,
        "targets": deepcopy(targets),
    }


def capability_routing_snapshot(tent_id, *, controllers=None):
    tent_id = validate_tent_id(tent_id)

    if tent_manager.get(tent_id) is None:
        raise KeyError(tent_id)

    cfg, _ = _registered_config(tent_id)
    targets = spiderfarmer_control_targets(controllers)

    payload = routing_snapshot_for_config(
        cfg,
        targets=targets,
    )
    payload.update({
        "success": True,
        "tent_id": tent_id,
    })
    return payload


def update_capability_routes(tent_id, data, *, controllers=None):
    """Persist routing metadata only. Never sends a hardware command."""

    tent_id = validate_tent_id(tent_id)

    if tent_manager.get(tent_id) is None:
        raise KeyError(tent_id)

    runtime_map = _runtime_map()
    cfg, runtime = _registered_config(tent_id, runtime_map)
    candidate = deepcopy(cfg)
    targets = spiderfarmer_control_targets(controllers)

    normalized = normalize_route_patch(
        data,
        targets,
    )

    routes = _apply_normalized_patch(
        candidate,
        normalized,
    )

    _assert_global_route_uniqueness(
        tent_id,
        routes,
        runtime_map=runtime_map,
    )

    _save_registered_config(
        tent_id,
        candidate,
        runtime=runtime,
    )

    payload = routing_snapshot_for_config(
        candidate,
        targets=targets,
    )
    payload.update({
        "success": True,
        "tent_id": tent_id,
        "changed": normalized,
    })
    return payload
