"""Spider Farmer SF.3B read-only controller/device diagnostics.

The purpose of SF.3B is to validate the SF.3A device model against the real
controller state before Growstar gains any Spider Farmer write path.

This module only reads the normalized state through services.spiderfarmer.
It never opens a controller socket, publishes MQTT, encodes commands or mutates
the canonical bridge state.
"""

from __future__ import annotations

from copy import deepcopy
import json

from services import spiderfarmer


def build_readout(path=None):
    """Return a compact diagnostic readout for all observed controllers."""

    controllers = []

    for controller in spiderfarmer.list_controllers(path):
        controller_result = {
            "id": controller.get("id"),
            "pid": controller.get("pid"),
            "prefix": controller.get("prefix"),
            "online": bool(controller.get("online")),
            "last_seen": controller.get("last_seen"),
            "device_count": controller.get("device_count", 0),
            "devices": [],
        }

        for device in controller.get("devices") or []:
            controller_result["devices"].append(
                _device_readout(device)
            )

        controllers.append(controller_result)

    return {
        "success": True,
        "phase": "SF.3B",
        "read_only": True,
        "controller_count": len(controllers),
        "controllers": controllers,
    }


def controller_readout(controller_id, path=None):
    """Return one controller readout by canonical id or PID."""

    controller = spiderfarmer.controller(
        controller_id,
        path,
    )

    if not controller:
        return None

    result = {
        "id": controller.get("id"),
        "pid": controller.get("pid"),
        "prefix": controller.get("prefix"),
        "online": bool(controller.get("online")),
        "last_seen": controller.get("last_seen"),
        "device_count": controller.get("device_count", 0),
        "devices": [],
    }

    for device in controller.get("devices") or []:
        result["devices"].append(
            _device_readout(device)
        )

    return result


def format_readout(readout):
    """Format a human-readable, phone-friendly diagnostic report."""

    if not isinstance(readout, dict):
        return "Spider Farmer SF.3B: kein gültiger Readout"

    lines = [
        "Spider Farmer SF.3B READ-ONLY",
        f"Controller: {readout.get('controller_count', 0)}",
    ]

    for controller in readout.get("controllers") or []:
        lines.extend([
            "",
            (
                "CONTROLLER "
                f"{controller.get('id') or '--'} "
                f"PID={controller.get('pid') or '--'} "
                f"ONLINE={'yes' if controller.get('online') else 'no'}"
            ),
            f"last_seen={controller.get('last_seen') or '--'}",
            f"device_count={controller.get('device_count', 0)}",
        ])

        for device in controller.get("devices") or []:
            lines.extend(
                _format_device(device)
            )

    return "\n".join(lines)


def to_json(readout, *, indent=2):
    return json.dumps(
        readout,
        indent=indent,
        ensure_ascii=False,
        sort_keys=False,
    )


def _device_readout(device):
    result = {
        "id": device.get("id"),
        "kind": device.get("kind"),
        "label": device.get("label"),
        "read_only": bool(device.get("read_only", True)),
        "available": bool(device.get("available", True)),
        "capabilities": list(
            device.get("capabilities") or []
        ),
        "effective": deepcopy(
            device.get("effective") or {}
        ),
    }

    channels = []

    for channel in device.get("channels") or []:
        channels.append({
            "id": channel.get("id"),
            "channel": channel.get("channel"),
            "kind": channel.get("kind"),
            "label": channel.get("label"),
            "read_only": bool(channel.get("read_only", True)),
            "available": bool(channel.get("available", True)),
            "capabilities": list(
                channel.get("capabilities") or []
            ),
            "effective": deepcopy(
                channel.get("effective") or {}
            ),
        })

    if channels:
        result["channels"] = channels

    return result


def _format_device(device):
    lines = [
        "",
        (
            f"  {device.get('id') or '--'}"
            f"  [{', '.join(device.get('capabilities') or [])}]"
        ),
    ]

    effective = device.get("effective") or {}

    if effective:
        for key, value in effective.items():
            if isinstance(value, (dict, list)):
                compact = json.dumps(
                    value,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                lines.append(
                    f"    {key}={compact}"
                )
            else:
                lines.append(
                    f"    {key}={value}"
                )
    else:
        lines.append("    effective={} ")

    for channel in device.get("channels") or []:
        lines.append(
            (
                f"    {channel.get('id') or '--'}"
                f"  [{', '.join(channel.get('capabilities') or [])}]"
            )
        )

        for key, value in (
            channel.get("effective") or {}
        ).items():
            lines.append(
                f"      {key}={value}"
            )

    return lines
