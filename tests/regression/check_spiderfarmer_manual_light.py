#!/usr/bin/env python3
"""Offline regression for SF.4D.13 confirmed production light control."""

from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge.spiderfarmer.command_model import (
    SpiderFarmerCommandError,
    compile_controller_command,
    compile_manual_light_command,
)
from core.controller_setpoints import controller_schema_for_family


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    schema = controller_schema_for_family("light", {"level"})
    require(
        schema["level"]["min"] == 11
        and schema["level"]["max"] == 100,
        "Zentrale Licht-Skala ist auf die reale 11..100-Prozent-Range begrenzt",
    )

    direct = compile_manual_light_command(
        pid="744DBD59D734",
        setpoints={
            "modeType": 0,
            "mOnOff": 1,
            "mLevel": 50,
        },
    )
    require(
        direct["payload"]["params"] == {
            "keyPath": ["device", "light"],
            "light": {
                "modeType": 0,
                "mOnOff": 1,
                "mLevel": 50,
            },
        },
        "Bestätigter manueller Licht-Payload bleibt minimal und exakt",
    )
    require(
        direct.get("diagnostic") == "confirmed_manual_light",
        "Manueller Licht-Test ist als hardwarebestätigt markiert",
    )

    for level in (11, 12, 15, 50, 75, 100):
        compile_manual_light_command(
            pid="744DBD59D734",
            setpoints={
                "modeType": 0,
                "mOnOff": 1,
                "mLevel": level,
            },
        )
    print("✅ Licht-mLevel 11..100 wird akzeptiert")

    for level in (0, 9, 10, 101, 11.5):
        try:
            compile_manual_light_command(
                pid="744DBD59D734",
                setpoints={
                    "modeType": 0,
                    "mOnOff": 1,
                    "mLevel": level,
                },
            )
        except SpiderFarmerCommandError:
            pass
        else:
            raise AssertionError(
                f"Ungültiger Licht-mLevel wurde akzeptiert: {level!r}"
            )
    print("✅ Werte unter 11 und über 100 werden blockiert")

    with tempfile.TemporaryDirectory() as td:
        capture = Path(td) / "raw_frames.jsonl"

        # Kein brauchbares Capture: Produktion muss trotzdem über den
        # hardwarebestätigten stabilen Envelope schreiben können.
        capture.write_text(
            json.dumps({
                "ts": "2026-08-23T21:55:00Z",
                "direction": "up",
                "session_id": "744dbd59d734",
                "topic": "SF/GGS/CB/API/UP/744DBD59D734",
                "payload": {"method": "getDevSta"},
            }) + "\n",
            encoding="utf-8",
        )

        fallback = compile_controller_command(
            capture,
            pid="744DBD59D734",
            module="light",
            setpoints={"level": 75},
        )
        require(
            fallback["payload"]["params"] == {
                "keyPath": ["device", "light"],
                "light": {
                    "modeType": 0,
                    "mOnOff": 1,
                    "mLevel": 75,
                },
            }
            and fallback.get("diagnostic") == "confirmed_manual_light_fallback",
            "Produktionspfad schreibt Licht ohne Capture über den bestätigten manuellen Fallback",
        )

        # Mit echtem Template darf keine alte Spider-Farmer-Automatik
        # zurückgesendet werden.
        capture.write_text(
            json.dumps({
                "ts": "2026-08-23T21:56:00Z",
                "direction": "down",
                "session_id": "744dbd59d734",
                "topic": "SF/GGS/CB/API/DOWN/744DBD59D734",
                "payload": {
                    "method": "setConfigField",
                    "params": {
                        "keyPath": ["device", "light"],
                        "light": {
                            "modeType": 2,
                            "mOnOff": 1,
                            "mLevel": 50,
                            "darkTemp": 28,
                            "offTemp": 32,
                            "timePeriod": [{
                                "enabled": 1,
                                "startTime": 21600,
                                "endTime": 64800,
                            }],
                            "ppfdPeriod": [{
                                "enabled": 1,
                                "startTime": 21600,
                                "endTime": 64800,
                            }],
                        },
                    },
                },
            }) + "\n",
            encoding="utf-8",
        )

        production = compile_controller_command(
            capture,
            pid="744DBD59D734",
            module="light",
            setpoints={"level": 25},
        )
        require(
            production["payload"]["params"] == {
                "keyPath": ["device", "light"],
                "light": {
                    "modeType": 0,
                    "mOnOff": 1,
                    "mLevel": 25,
                },
            },
            "Produktionspfad entfernt alte Licht-Automatik und sendet nur den manuellen Block",
        )

    print("✅ SF.4D.13 Licht-Produktionspfad vollständig erfolgreich")


if __name__ == "__main__":
    main()
