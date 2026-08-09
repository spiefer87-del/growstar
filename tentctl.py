#!/usr/bin/env python3
"""Lokale Growstar-Zeltverwaltung – Multi-Tent Phase 3B.

Phase 3B erlaubt für zusätzliche Zelte ausschließlich hardwarelose Shadow-
Regelkreise. Es gibt absichtlich keinen CLI-Befehl, der control_enabled für
``tent_2`` oder weitere Zelte aktivieren kann.
"""

import argparse
from copy import deepcopy
import json
import sys

from core.config import config as default_config
from core.tent_config import (
    ensure_tent_config,
    load_tent_config,
    save_tent_config,
)
from core.tents import DEFAULT_TENT_ID, init_tents, manager


_SHADOW_CONTROL_KEYS = {
    "DAY_START_MIN",
    "NIGHT_START_MIN",
    "DAY_TEMP",
    "DAY_TEMP_TOL",
    "DAY_HUM",
    "DAY_HUM_TOL",
    "NIGHT_TEMP",
    "NIGHT_TEMP_TOL",
    "NIGHT_HUM",
    "NIGHT_HUM_TOL",
    "MIN_TEMP",
    "MAX_TEMP",
    "MAX_HUM",
    "TEMP_OFFSET",
    "HUM_OFFSET",
    "RAMP_DURATION_MIN",
    "RAMP_ENABLED",
    "SENSOR_UPDATE_INTERVAL_SEC",
    "DEVICE_MODES",
    "DEVICE_PARAMS",
    "DEVICE_ENV_CONFIG",
}


def _print(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _require_tent(tent_id):
    tent = manager.get(tent_id)
    if tent is None:
        raise KeyError(f"Unbekanntes Zelt '{tent_id}'")
    return tent


def _load_config(tent_id):
    if tent_id == DEFAULT_TENT_ID:
        return default_config
    return load_tent_config(tent_id)


def _save_extra_config(tent_id, cfg):
    if tent_id == DEFAULT_TENT_ID:
        raise ValueError(
            "tent_1 bitte weiterhin über die bestehende Growstar-Konfiguration ändern"
        )
    return save_tent_config(tent_id, cfg)


def cmd_list(_args):
    init_tents()
    _print(manager.snapshot())


def cmd_add(args):
    init_tents()
    tent = manager.add_tent(
        args.tent_id,
        name=args.name or args.tent_id,
        enabled=True,
        shadow_enabled=False,
        control_enabled=False,
    )
    config_path = ensure_tent_config(args.tent_id)
    _print({
        "status": "created",
        "tent": tent,
        "config_file": config_path,
        "shadow_enabled": False,
        "hardware_control": False,
    })


def cmd_show(args):
    init_tents()
    tent = _require_tent(args.tent_id)

    result = {"tent": tent}
    if args.tent_id != DEFAULT_TENT_ID:
        result["config"] = load_tent_config(args.tent_id)
    else:
        result["config"] = "tent_1 verwendet weiterhin config.json"
    _print(result)


def cmd_rename(args):
    init_tents()
    _print(manager.rename_tent(args.tent_id, args.name))


def cmd_shadow(args):
    init_tents()
    enabled = args.state == "on"
    tent = manager.set_shadow_enabled(args.tent_id, enabled)
    _print({
        "status": "shadow_updated",
        "tent": tent,
        "restart_required": True,
        "hardware_control": False,
    })


def cmd_clone_control(args):
    """Kopiert nur Regelparameter, niemals IP-/Relay-Ziele."""

    init_tents()
    _require_tent(args.source)
    _require_tent(args.target)

    if args.target == DEFAULT_TENT_ID:
        raise ValueError("tent_1 darf nicht Ziel eines Shadow-Clones sein")

    source = _load_config(args.source)
    target = load_tent_config(args.target)

    copied = []
    for key in sorted(_SHADOW_CONTROL_KEYS):
        if key not in source:
            continue
        target[key] = deepcopy(source[key])
        copied.append(key)

    # Sensorquellen werden standardmäßig NICHT kopiert. Zwei Zelte sollen
    # niemals versehentlich denselben Sensor erben. Nur explizit anfordern.
    if args.include_sensors:
        target["SENSOR_ASSIGNMENTS"] = deepcopy(
            source.get("SENSOR_ASSIGNMENTS", {})
        )
        copied.append("SENSOR_ASSIGNMENTS")

    # Defensive Garantie: Hardwareziele werden aus dem Ziel entfernt, selbst
    # falls die Datei vorher manuell solche Felder enthielt.
    removed_hardware_keys = []
    for key in list(target):
        if key.startswith("IP_") or key.startswith("RELAY_"):
            removed_hardware_keys.append(key)
            target.pop(key, None)

    path = _save_extra_config(args.target, target)
    _print({
        "status": "control_config_cloned",
        "source": args.source,
        "target": args.target,
        "copied_keys": copied,
        "removed_hardware_keys": sorted(removed_hardware_keys),
        "config_file": path,
        "hardware_control": False,
    })


def cmd_sensor(args):
    init_tents()
    _require_tent(args.tent_id)

    if args.tent_id == DEFAULT_TENT_ID:
        raise ValueError(
            "Sensorzuweisungen von tent_1 bitte weiterhin über die bestehende UI ändern"
        )

    if args.sensor not in {"temperature", "humidity"}:
        raise ValueError("sensor muss 'temperature' oder 'humidity' sein")

    cfg = load_tent_config(args.tent_id)
    assignments = cfg.setdefault("SENSOR_ASSIGNMENTS", {})

    if args.clear:
        assignments.pop(args.sensor, None)
        action = "cleared"
    else:
        if not args.source_id:
            raise ValueError("source_id fehlt")

        field = args.field or (
            "temperature" if args.sensor == "temperature" else "humidity"
        )
        assignment = {
            "source_id": args.source_id,
            "field": field,
        }
        if args.label:
            assignment["label"] = args.label

        assignments[args.sensor] = assignment
        action = "assigned"

    path = save_tent_config(args.tent_id, cfg)
    _print({
        "status": action,
        "tent_id": args.tent_id,
        "sensor": args.sensor,
        "assignment": assignments.get(args.sensor),
        "config_file": path,
        "restart_required": True,
        "hardware_control": False,
    })


def build_parser():
    parser = argparse.ArgumentParser(description="Growstar Tent-Verwaltung")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="Zelte auflisten")
    p_list.set_defaults(func=cmd_list)

    p_add = sub.add_parser("add", help="Neues, hardware-inaktives Zelt anlegen")
    p_add.add_argument("tent_id")
    p_add.add_argument("--name")
    p_add.set_defaults(func=cmd_add)

    p_show = sub.add_parser("show", help="Zelt anzeigen")
    p_show.add_argument("tent_id")
    p_show.set_defaults(func=cmd_show)

    p_rename = sub.add_parser("rename", help="Zelt umbenennen")
    p_rename.add_argument("tent_id")
    p_rename.add_argument("name")
    p_rename.set_defaults(func=cmd_rename)

    p_shadow = sub.add_parser(
        "shadow",
        help="Shadow-Regelkreis eines zusätzlichen Zeltes ein/aus",
    )
    p_shadow.add_argument("tent_id")
    p_shadow.add_argument("state", choices=("on", "off"))
    p_shadow.set_defaults(func=cmd_shadow)

    p_clone = sub.add_parser(
        "clone-control",
        help="Regelparameter ohne Hardware-Adressen in ein Shadow-Zelt kopieren",
    )
    p_clone.add_argument("target")
    p_clone.add_argument("--source", default=DEFAULT_TENT_ID)
    p_clone.add_argument(
        "--include-sensors",
        action="store_true",
        help="Sensorzuweisungen bewusst mitkopieren",
    )
    p_clone.set_defaults(func=cmd_clone_control)

    p_sensor = sub.add_parser(
        "sensor",
        help="Sensorquelle eines Shadow-Zeltes zuweisen/entfernen",
    )
    p_sensor.add_argument("tent_id")
    p_sensor.add_argument("sensor", choices=("temperature", "humidity"))
    p_sensor.add_argument("source_id", nargs="?")
    p_sensor.add_argument("--field")
    p_sensor.add_argument("--label")
    p_sensor.add_argument("--clear", action="store_true")
    p_sensor.set_defaults(func=cmd_sensor)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        args.func(args)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
