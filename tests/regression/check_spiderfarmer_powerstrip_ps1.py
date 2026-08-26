#!/usr/bin/env python3
"""Growstar SF.PS1 base regression."""

import json
from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge.spiderfarmer.powerstrip_command import (
    compile_outlet_power_command,
    is_powerstrip_prefix,
    normalize_outlet,
    normalize_power,
)


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    require(normalize_outlet("o5") == "O5", "Outlet-Namen werden kanonisch normalisiert")
    require(normalize_power(True) == 1, "EIN wird zu mOnOff=1")
    require(normalize_power("aus") == 0, "AUS wird zu mOnOff=0")
    require(is_powerstrip_prefix("PS"), "Prefix PS bleibt zulässig")
    require(is_powerstrip_prefix("PS5"), "Realer PS5-Prefix wird zugelassen")
    require(is_powerstrip_prefix("PS10"), "PS10-Prefix wird zugelassen")
    require(not is_powerstrip_prefix("CB"), "CB bleibt ausgeschlossen")

    with tempfile.TemporaryDirectory() as temp_dir:
        capture = Path(temp_dir) / "raw_frames.jsonl"
        capture.write_text(
            json.dumps({
                "direction": "up",
                "topic": "SF/GGS/PS5/API/UP/7C2C67F2C5B8",
                "payload": {
                    "method": "getDevSta",
                    "pid": "7C2C67F2C5B8",
                    "uid": "31049",
                },
            }) + "\n",
            encoding="utf-8",
        )

        compiled = compile_outlet_power_command(
            capture,
            pid="7C2C67F2C5B8",
            outlet="O4",
            power=False,
            topic="SF/GGS/PS5/API/DOWN/7C2C67F2C5B8",
        )

    payload = compiled["payload"]
    params = payload["params"]

    require(
        compiled["topic"] == "SF/GGS/PS5/API/DOWN/7C2C67F2C5B8",
        "PS5-DOWN-Topic bleibt exakt erhalten",
    )
    require(
        params["keyPath"] == ["outlet", "O4"],
        "Outlet-Write nutzt keyPath outlet/O4",
    )
    require(
        params["O4"] == {"modeType": 0, "mOnOff": 0},
        "Outlet-Write nutzt manuellen EIN/AUS-Minimalblock",
    )
    require(payload["uid"] == "31049", "UID kommt aus beobachtetem Traffic")
    print("✅ Growstar SF.PS1 Basis vollständig geprüft")


if __name__ == "__main__":
    main()
