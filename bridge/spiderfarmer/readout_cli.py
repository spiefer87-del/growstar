#!/usr/bin/env python3
"""Phone-friendly Spider Farmer SF.3B read-only diagnostic CLI."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from bridge.spiderfarmer.readout import (
    build_readout,
    controller_readout,
    format_readout,
    to_json,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Read normalized Spider Farmer controller/device state "
            "without sending commands."
        )
    )

    parser.add_argument(
        "--controller",
        default=None,
        help="Controller-ID oder PID",
    )

    parser.add_argument(
        "--state",
        default=None,
        help="Optionaler Pfad zu spiderfarmer_state.json",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="JSON statt Text ausgeben",
    )

    args = parser.parse_args()

    if args.controller:
        controller = controller_readout(
            args.controller,
            args.state,
        )

        if controller is None:
            print(
                "Spider-Farmer-Controller nicht gefunden.",
                file=sys.stderr,
            )
            return 2

        payload = {
            "success": True,
            "phase": "SF.3B",
            "read_only": True,
            "controller_count": 1,
            "controllers": [controller],
        }
    else:
        payload = build_readout(
            args.state
        )

    if args.json:
        print(
            to_json(payload)
        )
    else:
        print(
            format_readout(payload)
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
