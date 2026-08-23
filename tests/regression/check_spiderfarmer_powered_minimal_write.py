#!/usr/bin/env python3
"""Regression for the isolated SF.4D.5 powered-minimal fan experiment."""

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

        observed = {
            "method": "setConfigField",
            "pid": "744DBD59D734",
            "params": {
                "keyPath": [
                    "device",
                    "fan",
                ],
                "fan": {
                    "modeType": 2,
                    "minSpeed": 3,
                    "maxSpeed": 8,
                    "shakeLevel": 4,
                    "natural": 1,
                    "timePeriod": [
                        {
                            "enabled": 1,
                            "weekmask": 127,
                            "startTime": 21600,
                            "endTime": 82920,
                        }
                    ],
                    "mOnOff": 1,
                    "mLevel": 5,
                    "cycleTime": {
                        "weekmask": 127,
                        "startTime": 20100,
                        "openDur": 90,
                        "closeDur": 270,
                        "times": 52,
                    },
                },
            },
            "msgId": "1787442346877",
            "uid": "31049",
        }

        capture.write_text(
            json.dumps(
                {
                    "ts": "2026-08-22T23:45:46Z",
                    "direction": "down",
                    "session_id": "744dbd59d734",
                    "topic": "SF/GGS/CB/API/DOWN/744DBD59D734",
                    "payload": observed,
                }
            ) + "\n",
            encoding="utf-8",
        )

        compiled = compile_powered_minimal_fan_command(
            capture,
            pid="744DBD59D734",
            setpoints={
                "level": 7,
            },
        )

        payload = compiled["payload"]

        require(
            payload["method"] == "setConfigField"
            and payload["pid"] == "744DBD59D734"
            and payload["msgId"] == "1787442346877"
            and payload["uid"] == "31049",
            "SF.4D.5 erhält den real beobachteten äußeren Command-Envelope",
        )

        require(
            payload["params"]["keyPath"] == [
                "device",
                "fan",
            ],
            "SF.4D.5 erhält den real beobachteten keyPath",
        )

        require(
            payload["params"]["fan"] == {
                "mOnOff": 1,
                "mLevel": 7,
            },
            "SF.4D.5-Diagnose folgt der korrigierten Zuordnung mOnOff=1 plus mLevel=7",
        )

        for forbidden in (
            "modeType",
            "minSpeed",
            "maxSpeed",
            "shakeLevel",
            "natural",
            "timePeriod",
            "cycleTime",
        ):
            require(
                forbidden not in payload["params"]["fan"],
                f"SF.4D.5 sendet {forbidden} nicht mit",
            )

        require(
            compiled["changed_fields"] == {
                "mOnOff": 1,
                "mLevel": 7,
            },
            "Diagnose-Rückgabe benennt die korrigierten tatsächlich gesendeten Fan-Felder",
        )

        for invalid in (
            {"level": 0},
            {"level": 11},
            {"level": 60},
            {"oscillation": 0},
            {"oscillation": 11},
        ):
            try:
                compile_powered_minimal_fan_command(
                    capture,
                    pid="744DBD59D734",
                    setpoints=invalid,
                )
            except SpiderFarmerCommandError:
                pass
            else:
                raise AssertionError(
                    f"Ungültiger SF.4D.5 Fan-Sollwert akzeptiert: {invalid}"
                )

        print(
            "✅ SF.4D.5 übernimmt die zentrale Fan-L1-bis-L10-Validierung"
        )

        try:
            compile_powered_minimal_fan_command(
                capture,
                pid="744DBD59D734",
                setpoints={
                    "level": 7,
                    "oscillation": 5,
                },
            )
        except SpiderFarmerCommandError:
            pass
        else:
            raise AssertionError(
                "SF.4D.5 akzeptierte mehr als einen Diagnose-Sollwert"
            )

        print(
            "✅ SF.4D.5 erlaubt pro realem Diagnoseversuch exakt einen Sollwert"
        )

    proxy_text = (
        ROOT
        / "bridge/spiderfarmer/command_proxy.py"
    ).read_text(
        encoding="utf-8"
    )

    require(
        '"set_controller"' in proxy_text
        and '"test_controller_minimal"' in proxy_text
        and '"test_controller_minimal_powered"' in proxy_text,
        "SF.4D.5 ergänzt den bestehenden Proxy ohne SF.4D.4 oder Produktionspfad zu entfernen",
    )

    require(
        "compile_controller_command(" in proxy_text
        and "compile_minimal_controller_command(" in proxy_text
        and "compile_powered_minimal_fan_command(" in proxy_text,
        "Produktions-, SF.4D.4- und SF.4D.5-Compiler bleiben getrennte Pfade",
    )

    require(
        'if module != "fan":' in proxy_text,
        "Powered-Minimal-Diagnose ist im Proxy ausdrücklich fan-only",
    )

    print(
        "✅ Spider Farmer SF.4D.5 Powered-Minimal Regression vollständig erfolgreich"
    )


if __name__ == "__main__":
    main()
