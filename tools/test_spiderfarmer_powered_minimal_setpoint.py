#!/usr/bin/env python3
"""One-off SF.4D.5 powered-minimal fan write experiment.

This tool is diagnostic-only. It never calls the normal Growstar set_controller
action.

Example:
    python3 tools/test_spiderfarmer_powered_minimal_setpoint.py \
        --controller 744dbd59d734 \
        --pid 744DBD59D734 \
        --level 7 \
        --yes
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = PROJECT_DIR / "instance" / "spiderfarmer"


def command_socket_path():
    configured = str(
        os.getenv("GROWSTAR_SF_COMMAND_SOCKET") or ""
    ).strip()

    if configured:
        return Path(configured).expanduser().resolve()

    state_dir = Path(
        os.getenv(
            "GROWSTAR_SF_STATE_DIR",
            str(DEFAULT_STATE_DIR),
        )
    ).expanduser().resolve()

    return state_dir / "command.sock"


def parse_args():
    parser = argparse.ArgumentParser(
        description="SF.4D.5 powered-minimal fan write experiment",
    )
    parser.add_argument("--controller", required=True)
    parser.add_argument("--pid", required=True)
    parser.add_argument("--level", type=int)
    parser.add_argument("--oscillation", type=int)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="required acknowledgement that this sends one real controller write",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.yes:
        raise SystemExit(
            "Abbruch: --yes fehlt. Dieser Test sendet einen echten "
            "Spider-Farmer-Schreibbefehl."
        )

    setpoints = {}

    if args.level is not None:
        setpoints["level"] = args.level

    if args.oscillation is not None:
        setpoints["oscillation"] = args.oscillation

    if len(setpoints) != 1:
        raise SystemExit(
            "Für SF.4D.5 genau EINEN Wert angeben: "
            "--level ODER --oscillation."
        )

    request = {
        "action": "test_controller_minimal_powered",
        "controller_id": args.controller.strip().lower(),
        "pid": args.pid.strip().upper(),
        "module": "fan",
        "setpoints": setpoints,
    }

    path = command_socket_path()

    client = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_STREAM,
    )
    client.settimeout(3.0)

    try:
        client.connect(str(path))

        client.sendall(
            json.dumps(
                request,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8") + b"\n"
        )

        chunks = bytearray()

        while b"\n" not in chunks:
            part = client.recv(65536)

            if not part:
                break

            chunks.extend(part)

        if not chunks:
            raise RuntimeError(
                "Keine Antwort vom Spider-Farmer-Command-Socket"
            )

        response = json.loads(
            bytes(chunks)
            .split(b"\n", 1)[0]
            .decode("utf-8")
        )

    finally:
        client.close()

    print(
        json.dumps(
            response,
            indent=2,
            ensure_ascii=False,
        )
    )

    return 0 if response.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
