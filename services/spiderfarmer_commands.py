"""Growstar-side Spider Farmer command adapter for SF.4D.

The web/control process never speaks MQTT and never owns the controller socket.
It sends one small, validated JSON request to the already-running local bridge
through its private UNIX command socket.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket


_PROJECT_DIR = Path(__file__).resolve().parents[1]
_DEFAULT_STATE_DIR = _PROJECT_DIR / "instance" / "spiderfarmer"


def state_dir():
    return Path(
        os.getenv(
            "GROWSTAR_SF_STATE_DIR",
            str(_DEFAULT_STATE_DIR),
        )
    ).expanduser().resolve()


def command_socket_path():
    configured = str(
        os.getenv("GROWSTAR_SF_COMMAND_SOCKET") or ""
    ).strip()

    if configured:
        return Path(configured).expanduser().resolve()

    return state_dir() / "command.sock"


def send_controller_setpoints(
    *,
    controller_id,
    pid,
    module,
    setpoints,
    timeout=3.0,
):
    request = {
        "action": "set_controller",
        "controller_id": str(controller_id or "").strip().lower(),
        "pid": str(pid or "").strip().upper(),
        "module": str(module or "").strip(),
        "setpoints": dict(setpoints or {}),
    }

    path = command_socket_path()

    client = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_STREAM,
    )
    client.settimeout(float(timeout))

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
            if len(chunks) > 65536:
                raise RuntimeError(
                    "Spider-Farmer command response too large"
                )

        if not chunks:
            raise RuntimeError(
                "Spider-Farmer bridge returned no command response"
            )

        response = json.loads(
            bytes(chunks).split(b"\n", 1)[0].decode("utf-8")
        )

        if not isinstance(response, dict):
            raise RuntimeError(
                "Invalid Spider-Farmer command response"
            )

        return response

    finally:
        client.close()
