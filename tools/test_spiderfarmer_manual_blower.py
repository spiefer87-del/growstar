#!/usr/bin/env python3
"""Send one controlled SF.4D.9 manual blower diagnostic command."""

import argparse
import json
import socket

DEFAULT_SOCKET = "instance/spiderfarmer/command.sock"
DEFAULT_CONTROLLER = "744dbd59d734"
DEFAULT_PID = "744DBD59D734"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-speed", type=int, required=True)
    parser.add_argument("--controller-id", default=DEFAULT_CONTROLLER)
    parser.add_argument("--pid", default=DEFAULT_PID)
    parser.add_argument("--socket", default=DEFAULT_SOCKET)
    args = parser.parse_args()

    if not 0 <= args.max_speed <= 100:
        parser.error("--max-speed muss zwischen 0 und 100 liegen")

    request = {
        "action": "test_controller_manual_blower",
        "controller_id": args.controller_id,
        "pid": args.pid,
        "module": "blower",
        "setpoints": {
            "modeType": 0,
            "mOnOff": 1,
            "maxSpeed": args.max_speed,
        },
    }

    print("=== REQUEST ===")
    print(json.dumps(request, indent=2))

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(5)
    client.connect(args.socket)
    client.sendall((json.dumps(request, separators=(",", ":")) + "\n").encode())

    response = b""
    while b"\n" not in response:
        chunk = client.recv(65536)
        if not chunk:
            break
        response += chunk
    client.close()

    print("\n=== RESPONSE ===")
    print(response.decode("utf-8", errors="replace"))


if __name__ == "__main__":
    main()
