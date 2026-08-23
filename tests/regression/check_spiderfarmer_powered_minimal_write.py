#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge.spiderfarmer.command_model import (
    SpiderFarmerCommandError,
    compile_powered_minimal_fan_command,
)


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    with tempfile.TemporaryDirectory() as td:
        capture = Path(td) / "raw_frames.jsonl"

        payload = {
            "method": "setConfigField",
            "pid": "744DBD59D734",
            "params": {
                "keyPath": ["device", "fan"],
                "fan": {
                    "modeType": 2,
                    "minSpeed": 3,
                    "maxSpeed": 8,
                    "shakeLevel": 4,
                    "natural": 1,
                    "timePeriod": [{"enabled": 1}],
                    "mOnOff": 1,
                    "mLevel": 5,
                    "cycleTime": {"weekmask": 127},
                },
            },
            "msgId": "1787442346877",
            "uid": "31049",
        }

        capture.write_text(
            json.dumps({
                "ts": "2026-08-22T23:45:46Z",
                "direction": "down",
                "session_id": "744dbd59d734",
                "topic": "SF/GGS/CB/API/DOWN/744DBD59D734",
                "payload": payload,
            }) + "\n",
            encoding="utf-8",
        )

        result = compile_powered_minimal_fan_command(
            capture,
            pid="744DBD59D734",
            setpoints={"level": 7},
        )

        out = result["payload"]
        require(
            out["params"]["fan"] == {"mOnOff": 1, "maxSpeed": 7},
            "SF.4D.5 sendet exakt mOnOff=1 plus maxSpeed",
        )

        fan = out["params"]["fan"]
        for forbidden in (
            "modeType",
            "minSpeed",
            "shakeLevel",
            "natural",
            "timePeriod",
            "mLevel",
            "cycleTime",
        ):
            require(forbidden not in fan, f"SF.4D.5 sendet {forbidden} nicht mit")

        try:
            compile_powered_minimal_fan_command(
                capture,
                pid="744DBD59D734",
                setpoints={"level": 60},
            )
        except SpiderFarmerCommandError:
            pass
        else:
            raise AssertionError("Ungültiges L60 wurde akzeptiert")

        print("✅ L1-bis-L10-Validierung bleibt aktiv")

    print("✅ Spider Farmer SF.4D.5 Powered-Minimal Regression vollständig erfolgreich")


if __name__ == "__main__":
    main()
