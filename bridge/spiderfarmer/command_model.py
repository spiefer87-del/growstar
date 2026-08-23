"""Observed-template Spider Farmer command compiler for SF.4D.

The command compiler intentionally does not invent undocumented GGS payloads.
It reuses the latest real DOWN/setConfigField payload previously captured from
the Spider Farmer app/cloud and changes only the small set of fields that
Growstar owns.

This preserves firmware-specific fields, schedules and flags that Growstar does
not understand yet.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from .state_model import parse_topic


_FIELD_MAP = {
    "fan": {
        "level": "maxSpeed",
        "oscillation": "shakeLevel",
    },
    "blower": {
        "level": "maxSpeed",
    },
    "light": {
        "level": "mLevel",
    },
    "light2": {
        "level": "mLevel",
    },
}


class SpiderFarmerCommandError(RuntimeError):
    pass


def _payload_matches_module(payload, module):
    if not isinstance(payload, dict):
        return False
    if payload.get("method") != "setConfigField":
        return False

    params = payload.get("params")
    if not isinstance(params, dict):
        return False

    if isinstance(params.get(module), dict):
        return True

    key_path = params.get("keyPath")
    return (
        isinstance(key_path, list)
        and key_path
        and str(key_path[-1]) == module
        and isinstance(params.get(module), dict)
    )


def _capture_candidates(capture_path):
    """Return capture files from newest generation to oldest generation."""

    capture_path = Path(capture_path)
    candidates = [capture_path]

    rotated = Path(str(capture_path) + ".1")
    if rotated.exists():
        candidates.append(rotated)

    return candidates


def find_latest_template(capture_path, *, pid, module):
    """Return latest observed real setConfigField command for module/PID."""

    capture_path = Path(capture_path)
    pid = str(pid or "").strip().upper()
    module = str(module or "").strip()

    if not pid:
        raise SpiderFarmerCommandError("Controller-PID fehlt")
    if module not in _FIELD_MAP:
        raise SpiderFarmerCommandError(
            f"Modul {module!r} wird noch nicht geschrieben"
        )

    readable_capture_seen = False
    last_read_error = None

    # Newest capture generation first; only then the older rotated generation.
    for candidate in _capture_candidates(capture_path):
        try:
            lines = candidate.read_text(encoding="utf-8").splitlines()
            readable_capture_seen = True
        except FileNotFoundError:
            continue
        except OSError as exc:
            last_read_error = exc
            continue

        for line in reversed(lines):
            try:
                row = json.loads(line)
            except (TypeError, ValueError):
                continue

            if not isinstance(row, dict) or row.get("direction") != "down":
                continue

            topic = str(row.get("topic") or "")
            topic_info = parse_topic(topic)

            if not topic_info or topic_info.get("pid") != pid:
                continue

            payload = row.get("payload")
            if not _payload_matches_module(payload, module):
                continue

            return {
                "topic": topic,
                "payload": deepcopy(payload),
                "observed_at": row.get("ts"),
                "session_id": row.get("session_id"),
            }

    if not readable_capture_seen and last_read_error is not None:
        raise SpiderFarmerCommandError(
            f"Spider-Farmer-Rohcapture nicht lesbar: {last_read_error}"
        ) from last_read_error

    if not readable_capture_seen:
        raise SpiderFarmerCommandError(
            f"Spider-Farmer-Rohcapture nicht gefunden: {capture_path}"
        )

    raise SpiderFarmerCommandError(
        f"Noch kein echtes setConfigField-Template für {module} / {pid} "
        "beobachtet. Einmal in der Spider-Farmer-App einen Wert dieses Geräts "
        "ändern und danach erneut versuchen."
    )


def compile_controller_command(
    capture_path,
    *,
    pid,
    module,
    setpoints,
):
    if not isinstance(setpoints, dict) or not setpoints:
        raise SpiderFarmerCommandError("Keine Controller-Sollwerte angegeben")

    field_map = _FIELD_MAP.get(str(module))
    if not field_map:
        raise SpiderFarmerCommandError(
            f"Modul {module!r} wird noch nicht geschrieben"
        )

    unknown = sorted(set(setpoints) - set(field_map))
    if unknown:
        raise SpiderFarmerCommandError(
            "Nicht unterstützte Sollwerte: " + ", ".join(unknown)
        )

    template = find_latest_template(
        capture_path,
        pid=pid,
        module=module,
    )

    payload = deepcopy(template["payload"])
    params = payload["params"]
    block = params.get(module)

    if not isinstance(block, dict):
        raise SpiderFarmerCommandError(
            f"Beobachtetes Template enthält keinen {module}-Block"
        )

    changed_fields = {}

    for name, value in setpoints.items():
        raw_field = field_map[name]
        block[raw_field] = value
        changed_fields[raw_field] = value

    return {
        "topic": template["topic"],
        "payload": payload,
        "observed_at": template.get("observed_at"),
        "session_id": template.get("session_id"),
        "module": module,
        "changed_fields": changed_fields,
    }
