"""Growstar-side adapter for Spider Farmer PS outlet commands."""

from __future__ import annotations

import json
import socket

from services.spiderfarmer_commands import command_socket_path


def send_outlet_power(
    *,
    controller_id,
    pid,
    outlet,
    power,
    timeout=3.0,
):
    request = {
        "action": "set_powerstrip_outlet",
        "controller_id": str(controller_id or "").strip().lower(),
        "pid": str(pid or "").strip().upper(),
        "outlet": str(outlet or "").strip().upper(),
        "power": power,
    }

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(float(timeout))

    try:
        client.connect(str(command_socket_path()))
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
                    "Spider-Farmer Power-Strip response too large"
                )

        if not chunks:
            raise RuntimeError(
                "Spider-Farmer bridge returned no Power-Strip response"
            )

        response = json.loads(
            bytes(chunks).split(b"\n", 1)[0].decode("utf-8")
        )
        if not isinstance(response, dict):
            raise RuntimeError(
                "Invalid Spider-Farmer Power-Strip response"
            )
        return response
    finally:
        client.close()
