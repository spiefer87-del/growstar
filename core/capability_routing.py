"""Device-bound controller assignments for Growstar SF.4B.1.

Architecture
------------
Power remains a separate actuator path (currently Shelly). A physical
controller device is assigned as ONE unit to ONE logical Growstar device.

Example:

    Growstar vent
      power      -> Shelly
      controller -> Spider Farmer fan
                    ├─ level
                    └─ oscillation

The controller capabilities cannot be split across different Growstar
devices. If the Spider Farmer fan is assigned to ``vent``, both level and
oscillation belong to that same logical device.

The model remains provider-neutral: future controller providers can expose a
compatible controller family and capabilities. Spider Farmer is only the first
provider.

SF.4B.1 is still configuration-only. No hardware command is sent.
"""

from __future__ import annotations

from copy import deepcopy

from core.config import config as default_config, save_config
from core.devices import DEVICE_META, DEVICE_NAMES, validate_device_name
from core.hardware_assignments import DEVICE_HARDWARE
from core.runtime import list_runtimes
from core.tent_config import ensure_tent_config, load_tent_config, save_tent_config
from core.tents import DEFAULT_TENT_ID, manager as tent_manager, validate_tent_id


CONFIG_KEY = "CONTROLLER_ASSIGNMENTS"
LEGACY_CONFIG_KEY = "CAPABILITY_ROUTES"

CAPABILITY_POWER = "power"
CAPABILITY_LEVEL = "level"
CAPABILITY_OSCILLATION = "oscillation"

FAMILY_LIGHT = "light"
FAMILY_FAN = "fan"
FAMILY_BLOWER = "blower"

# Logical Growstar devices that may receive a controller.
#
# A controller target must match the family AND provide every required
# capability. This prevents e.g. a light controller from being assigned to the
# exhaust fan merely because both happen to expose a generic "level".
DEVICE_CONTROLLER_REQUIREMENTS = {
    "light": {
        "family": FAMILY_LIGHT,
        "capabilities": (CAPABILITY_LEVEL,),
    },
    "light2": {
        "family": FAMILY_LIGHT,
        "capabilities": (CAPABILITY_LEVEL,),
    },
    "vent": {
        "family": FAMILY_FAN,
        "capabilities": (CAPABILITY_LEVEL, CAPABILITY_OSCILLATION),
    },
    "vent2": {
        "family": FAMILY_FAN,
        "capabilities": (CAPABILITY_LEVEL, CAPABILITY_OSCILLATION),
    },
    "fan": {
        "family": FAMILY_BLOWER,
        "capabilities": (CAPABILITY_LEVEL,),
    },
}


class CapabilityRouteConflictError(ValueError):
    """Compatibility name for a device-level controller conflict."""

    def __init__(self, target_id, *, owner=None, contender=None):
        self.capability = "controller"
        self.target_id = str(target_id)
        self.owner = deepcopy(owner)
        self.contender = deepcopy(contender)

        super().__init__(
            f"Controller {self.target_id} ist bereits einem anderen "
            "Growstar-Gerät zugeordnet."
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


def _controller_family(device_id):
    value = str(device_id or "").strip()

    if value in ("light", "light2"):
        return FAMILY_LIGHT
    if value == "fan":
        return FAMILY_FAN
    if value == "blower":
        return FAMILY_BLOWER
    return None


def spiderfarmer_control_targets(controllers=None):
    """Project normalized Spider Farmer devices into controller targets.

    One target represents one physical Spider Farmer device. Its capabilities
    are metadata of that single device and are never independently assignable.
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
            family = _controller_family(device_id)

            controller_capabilities = []

            if "level" in capabilities and family is not None:
                controller_capabilities.append(CAPABILITY_LEVEL)

            if (
                "oscillation_level" in capabilities
                and family == FAMILY_FAN
            ):
                controller_capabilities.append(CAPABILITY_OSCILLATION)

            if controller_capabilities:
                result.append({
                    "id": _target_id(controller_id, device_id),
                    "provider": "spiderfarmer",
                    "controller_id": controller_id,
                    "controller_pid": pid,
                    "device_id": device_id,
                    "family": family,
                    "label": (
                        f"{device.get('label') or device_id} · "
                        f"GGS {controller_id[-4:].upper()}"
                    ),
                    "capabilities": sorted(set(controller_capabilities)),
                    "online": online,
                    "writable": False,
                    "assignment_enabled": True,
                    "role": "device_controller",
                })

            # Future power actors remain visible in the inventory but do not
            # participate in controller assignment.
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
                    "family": None,
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
    return {
        "success": True,
        "phase": "SF.4B.1",
        "read_only": True,
        "command_transport_enabled": False,
        "targets": spiderfarmer_control_targets(controllers),
    }


def _target_map(targets):
    return {
        str(item.get("id") or ""): item
        for item in targets or []
        if isinstance(item, dict) and item.get("id")
    }


def _stored_assignments(cfg):
    value = cfg.get(CONFIG_KEY) if isinstance(cfg, dict) else None
    return deepcopy(value) if isinstance(value, dict) else {}


def _legacy_routes(cfg):
    value = cfg.get(LEGACY_CONFIG_KEY) if isinstance(cfg, dict) else None
    return deepcopy(value) if isinstance(value, dict) else {}


def _assignment_from_legacy(device, cfg):
    """Read an existing SF.4A/SF.4B per-capability mapping as one controller.

    A valid legacy mapping must point every configured controller capability of
    one logical device to the SAME target. This lets installations that already
    saved SF.4B mappings migrate without manual editing.
    """

    routes = _legacy_routes(cfg)
    raw = routes.get(device)

    if not isinstance(raw, dict):
        return None

    target_ids = set()
    providers = set()

    for capability in (
        CAPABILITY_LEVEL,
        CAPABILITY_OSCILLATION,
    ):
        assignment = raw.get(capability)
        if not isinstance(assignment, dict):
            continue

        target_id = str(assignment.get("target_id") or "").strip()
        if target_id:
            target_ids.add(target_id)
            providers.add(str(assignment.get("provider") or ""))

    if not target_ids:
        return None

    if len(target_ids) != 1:
        raise ValueError(
            f"{device}: bestehende Controller-Zuordnung ist auf mehrere "
            "physische Geräte verteilt. Bitte vor der Migration bereinigen."
        )

    return {
        "provider": next(iter(providers), ""),
        "target_id": next(iter(target_ids)),
        "source": "legacy_capability_routes",
    }


def controller_assignment_for_config(cfg, device):
    validate_device_name(device)

    stored = _stored_assignments(cfg).get(device)
    if isinstance(stored, dict) and stored.get("target_id"):
        return deepcopy(stored)

    return _assignment_from_legacy(device, cfg)


def _required_controller(device):
    validate_device_name(device)
    return deepcopy(DEVICE_CONTROLLER_REQUIREMENTS.get(device))


def _target_compatible(device, target):
    requirement = _required_controller(device)
    if not requirement:
        return False

    if not isinstance(target, dict):
        return False

    if not target.get("assignment_enabled"):
        return False

    if target.get("role") != "device_controller":
        return False

    if target.get("family") != requirement["family"]:
        return False

    available = set(target.get("capabilities") or [])
    required = set(requirement["capabilities"])

    return required.issubset(available)


def _normalize_controller_assignment(device, raw, target_map):
    validate_device_name(device)

    requirement = _required_controller(device)
    if requirement is None:
        raise ValueError(
            f"{device}: dieses Growstar-Gerät besitzt keine "
            "Controller-Zuordnung."
        )

    if raw in (None, "", False):
        return None

    if not isinstance(raw, dict):
        raise TypeError(
            f"{device}: Controller-Zuordnung muss ein JSON-Objekt sein."
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
            f"{device}: unbekanntes Controller-Ziel {target_id!r}"
        )

    if not _target_compatible(device, target):
        raise ValueError(
            f"{device}: Controller-Ziel {target_id!r} ist nicht vollständig "
            "mit diesem Growstar-Gerät kompatibel."
        )

    return {
        "provider": str(target.get("provider") or ""),
        "target_id": target_id,
    }


def normalize_route_patch(data, targets):
    """Normalize one device-level controller assignment update.

    The historical function name is retained so the existing route module does
    not need a parallel API. Accepted payload:

        {
          "controllers": {
            "vent": {"target_id": "..."},
            "vent2": null
          }
        }
    """

    if not isinstance(data, dict):
        raise TypeError(
            "Controller-Zuordnungs-Update muss ein JSON-Objekt sein."
        )

    raw_assignments = data.get("controllers")
    if raw_assignments is None:
        raw_assignments = data.get("assignments")

    # Compatibility for callers that still wrap values in "routes".
    if raw_assignments is None:
        raw_assignments = data.get("routes", data)

    if not isinstance(raw_assignments, dict):
        raise TypeError("controllers muss ein JSON-Objekt sein.")

    unknown_devices = sorted(
        set(raw_assignments) - set(DEVICE_NAMES)
    )
    if unknown_devices:
        raise ValueError(
            "Unbekannte Growstar-Geräte: " + ", ".join(unknown_devices)
        )

    target_map = _target_map(targets)
    normalized = {}

    for device, raw in raw_assignments.items():
        # Old SF.4B payload had:
        #   device -> {level:{target_id}, oscillation:{target_id}}
        # Accept it only if every provided capability points to one target.
        if (
            isinstance(raw, dict)
            and "target_id" not in raw
            and "target" not in raw
            and any(
                key in raw
                for key in (
                    CAPABILITY_LEVEL,
                    CAPABILITY_OSCILLATION,
                )
            )
        ):
            target_ids = {
                str(value.get("target_id") or "").strip()
                for value in raw.values()
                if isinstance(value, dict)
                and value.get("target_id")
            }

            if len(target_ids) > 1:
                raise ValueError(
                    f"{device}: Level und Oszillation dürfen nicht auf "
                    "verschiedene Controller verteilt werden."
                )

            raw = (
                {"target_id": next(iter(target_ids))}
                if target_ids
                else None
            )

        normalized[device] = _normalize_controller_assignment(
            device,
            raw,
            target_map,
        )

    _assert_local_target_uniqueness(normalized)
    return normalized


def _assert_local_target_uniqueness(assignments):
    owners = {}

    for device, assignment in assignments.items():
        if not assignment:
            continue

        target_id = assignment["target_id"]
        owner = owners.get(target_id)
        contender = {"device": device}

        if owner is not None and owner != contender:
            raise CapabilityRouteConflictError(
                target_id,
                owner=owner,
                contender=contender,
            )

        owners[target_id] = contender


def _apply_normalized_patch(cfg, normalized):
    assignments = _stored_assignments(cfg)

    for device, assignment in normalized.items():
        if assignment is None:
            assignments.pop(device, None)
        else:
            assignments[device] = deepcopy(assignment)

        # Once a device has been deliberately saved in the new model, remove
        # its obsolete per-capability legacy entry so two sources of truth
        # cannot diverge.
        legacy = cfg.get(LEGACY_CONFIG_KEY)
        if isinstance(legacy, dict):
            legacy.pop(device, None)
            if not legacy:
                cfg.pop(LEGACY_CONFIG_KEY, None)

    cfg[CONFIG_KEY] = assignments
    return assignments


def _all_effective_assignments(cfg):
    result = _stored_assignments(cfg)

    for device in DEVICE_CONTROLLER_REQUIREMENTS:
        if device in result:
            continue

        legacy = _assignment_from_legacy(device, cfg)
        if legacy:
            result[device] = legacy

    return result


def _assert_global_target_uniqueness(
    tent_id,
    candidate_cfg,
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
            cfg = candidate_cfg
        else:
            cfg, _ = _registered_config(
                other_tent_id,
                runtime_map,
            )

        assignments = _all_effective_assignments(cfg)

        for device, assignment in assignments.items():
            if not isinstance(assignment, dict):
                continue

            target_id = str(
                assignment.get("target_id") or ""
            ).strip()
            if not target_id:
                continue

            current = {
                "tent_id": other_tent_id,
                "device": device,
            }

            owner = owners.get(target_id)
            if owner is not None and owner != current:
                raise CapabilityRouteConflictError(
                    target_id,
                    owner=owner,
                    contender=current,
                )

            owners[target_id] = current


def controller_target_owners(*, runtime_map=None):
    """Return current owner metadata for every physical controller target."""

    runtime_map = runtime_map or _runtime_map()
    owners = {}

    tents = {
        str(item.get("id") or ""): item
        for item in tent_manager.list_tents()
        if isinstance(item, dict) and item.get("id")
    }

    for tent_id, tent in tents.items():
        cfg, _ = _registered_config(tent_id, runtime_map)
        assignments = _all_effective_assignments(cfg)

        for device, assignment in assignments.items():
            if not isinstance(assignment, dict):
                continue

            target_id = str(
                assignment.get("target_id") or ""
            ).strip()
            if not target_id:
                continue

            meta = DEVICE_META.get(device) or {}

            owners.setdefault(
                target_id,
                {
                    "tent_id": tent_id,
                    "tent_name": tent.get("name") or tent_id,
                    "device": device,
                    "device_label": meta.get("label") or device,
                },
            )

    return owners


def annotate_target_usage(targets, owners):
    result = []

    for raw_target in targets or []:
        if not isinstance(raw_target, dict):
            continue

        target = deepcopy(raw_target)
        owner = owners.get(str(target.get("id") or ""))
        target["owner"] = deepcopy(owner) if owner else None
        target["in_use"] = bool(owner)
        result.append(target)

    return result


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
    target_map = _target_map(targets)

    devices = {}

    for device in DEVICE_NAMES:
        meta = DEVICE_META.get(device) or {}
        requirement = _required_controller(device)
        assignment = (
            controller_assignment_for_config(cfg, device)
            if requirement
            else None
        )

        target = (
            target_map.get(assignment.get("target_id"))
            if isinstance(assignment, dict)
            else None
        )

        controller = {
            "supported": bool(requirement),
            "configured": bool(assignment),
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
            "family": (
                requirement.get("family")
                if requirement
                else None
            ),
            "required_capabilities": (
                list(requirement.get("capabilities") or [])
                if requirement
                else []
            ),
            "effective_capabilities": (
                list(target.get("capabilities") or [])
                if target
                else []
            ),
            "compatible": (
                _target_compatible(device, target)
                if target
                else True
            ),
            "source": (
                assignment.get("source", "controller_assignments")
                if assignment
                else None
            ),
        }

        devices[device] = {
            "device": device,
            "label": meta.get("label") or device,
            "icon": meta.get("icon") or "🔌",
            "power": _legacy_power_route(cfg, device),
            "controller": controller,
        }

    return {
        "phase": "SF.4B.1",
        "read_only_control_plane": True,
        "command_transport_enabled": False,
        "devices": devices,
        "targets": deepcopy(targets),
    }


def capability_routing_snapshot(tent_id, *, controllers=None):
    tent_id = validate_tent_id(tent_id)

    if tent_manager.get(tent_id) is None:
        raise KeyError(tent_id)

    runtime_map = _runtime_map()
    cfg, _ = _registered_config(tent_id, runtime_map)

    targets = spiderfarmer_control_targets(controllers)
    owners = controller_target_owners(runtime_map=runtime_map)
    targets = annotate_target_usage(targets, owners)

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
    """Persist controller-device assignments only. Never sends a command."""

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

    _apply_normalized_patch(
        candidate,
        normalized,
    )

    _assert_global_target_uniqueness(
        tent_id,
        candidate,
        runtime_map=runtime_map,
    )

    _save_registered_config(
        tent_id,
        candidate,
        runtime=runtime,
    )

    owners = controller_target_owners(runtime_map=runtime_map)
    annotated_targets = annotate_target_usage(
        targets,
        owners,
    )

    payload = routing_snapshot_for_config(
        candidate,
        targets=annotated_targets,
    )
    payload.update({
        "success": True,
        "tent_id": tent_id,
        "changed": normalized,
    })
    return payload
