#!/usr/bin/env python3
"""Regression for the isolated SF.4D.4 minimal-write experiment."""

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
    compile_minimal_controller_command,
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

        result = compile_minimal_controller_command(
            capture,
            pid="744DBD59D734",
            module="fan",
            setpoints={"level": 7},
        )

        out = result["payload"]

        require(
            out["method"] == "setConfigField"
            and out["pid"] == "744DBD59D734"
            and out["msgId"] == "1787442346877"
            and out["uid"] == "31049",
            "Minimaltest erhält den real beobachteten äußeren Command-Envelope",
        )
        require(
            out["params"]["keyPath"] == ["device", "fan"],
            "Minimaltest erhält den real beobachteten keyPath",
        )
        require(
            out["params"]["fan"] == {"maxSpeed": 7},
            "Minimaltest sendet im Fan-Block ausschließlich maxSpeed",
        )
        require(
            "modeType" not in out["params"]["fan"]
            and "cycleTime" not in out["params"]["fan"]
            and "timePeriod" not in out["params"]["fan"]
            and "natural" not in out["params"]["fan"],
            "Intervall, Standby, Natural-Wind und weitere Fan-Konfiguration werden nicht mitgesendet",
        )

        try:
            compile_minimal_controller_command(
                capture,
                pid="744DBD59D734",
                module="fan",
                setpoints={"level": 60},
            )
        except SpiderFarmerCommandError:
            pass
        else:
            raise AssertionError("Ungültiges L60 wurde im Minimaltest akzeptiert")

        print("✅ Minimaltest übernimmt weiterhin die zentrale L1-bis-L10-Validierung")

    proxy = (
        ROOT / "bridge/spiderfarmer/command_proxy.py"
    ).read_text(encoding="utf-8")

    require(
        '"test_controller_minimal"' in proxy,
        "Private Diagnose-Action ist registriert",
    )
    require(
        'action == "test_controller_minimal"' in proxy,
        "Diagnose-Action ist vom normalen set_controller-Pfad getrennt",
    )

    print("✅ Spider Farmer SF.4D.4 Minimal-Write Regression vollständig erfolgreich")


if __name__ == "__main__":
    main()
