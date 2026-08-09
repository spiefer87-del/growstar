#!/usr/bin/env python3
"""Kleine lokale Verwaltung für Growstar-Zelte (Phase 3).

Phase 3 erlaubt bewusst KEIN Aktivieren eines zweiten Hardware-Regelkreises.
Neue Zelte werden immer mit control_enabled=False angelegt.
"""

import argparse
import json
import sys

from core.tent_config import ensure_tent_config, load_tent_config
from core.tents import init_tents, manager


def _print(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_list(_args):
    init_tents()
    _print(manager.snapshot())


def cmd_add(args):
    init_tents()
    tent = manager.add_tent(
        args.tent_id,
        name=args.name or args.tent_id,
        enabled=True,
        control_enabled=False,
    )
    config_path = ensure_tent_config(args.tent_id)
    _print({
        "status": "created",
        "tent": tent,
        "config_file": config_path,
        "hardware_control": False,
    })


def cmd_show(args):
    init_tents()
    tent = manager.get(args.tent_id)
    if tent is None:
        raise KeyError(f"Unbekanntes Zelt '{args.tent_id}'")

    result = {"tent": tent}
    if args.tent_id != manager.default_tent_id():
        result["config"] = load_tent_config(args.tent_id)
    else:
        result["config"] = "tent_1 verwendet weiterhin config.json"
    _print(result)


def cmd_rename(args):
    init_tents()
    _print(manager.rename_tent(args.tent_id, args.name))


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
