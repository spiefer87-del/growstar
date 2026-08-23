#!/usr/bin/env python3
"""Regression for the hardware-confirmed SF.4D.11 production blower path."""

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
    compile_controller_command,
)
from core.controller_setpoints import controller_schema_for_family


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    schema = controller_schema_for_family("blower", ["level"])
    require(
        schema["level"]["min"] == 25
        and schema["level"]["max"] == 100
        and schema["level"]["unit"] == "%",
        "Growstar-Blower-Regler verwendet 25..100 Prozent",
    )

    with tempfile.TemporaryDirectory() as tmp:
        capture = Path(tmp) / "raw_frames.jsonl"
        capture.write_text(
            json.dumps(
                {
                    "ts": "2026-08-23T20:00:00Z",
                    "direction": "down",
                    "session_id": "744dbd59d734",
                    "topic": "SF/GGS/CB/API/DOWN/744DBD59D734",
                    "payload": {
                        "method": "setConfigField",
                        "params": {
                            "keyPath": ["device", "blower"],
                            "blower": {
                                "modeType": 3,
                                "mOnOff": 1,
                                "mLevel": 25,
                                "minSpeed": 25,
                                "maxSpeed": 100,
                                "natural": 1,
                            },
                        },
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

        compiled = compile_controller_command(
            capture,
            pid="744DBD59D734",
            module="blower",
            setpoints={"level": 80},
        )

        require(
            compiled["payload"]["params"] == {
                "keyPath": ["device", "blower"],
                "blower": {
                    "modeType": 0,
                    "mOnOff": 1,
                    "mLevel": 80,
                },
            },
            "Produktionspfad sendet Blower minimal manuell mit mLevel",
        )
        require(
            "minSpeed" not in compiled["payload"]["params"]["blower"]
            and "maxSpeed" not in compiled["payload"]["params"]["blower"]
            and "natural" not in compiled["payload"]["params"]["blower"],
            "Produktionspfad sendet keine alte Spider-Farmer-Automatik zurück",
        )

    with tempfile.TemporaryDirectory() as tmp:
        missing = Path(tmp) / "missing.jsonl"
        fallback = compile_controller_command(
            missing,
            pid="744DBD59D734",
            module="blower",
            setpoints={"level": 40},
        )
        require(
            fallback["payload"]["params"]["blower"]
            == {"modeType": 0, "mOnOff": 1, "mLevel": 40}
            and fallback.get("diagnostic") == "confirmed_manual_blower_fallback",
            "Bestätigter Blower-Pfad funktioniert auch ohne Capture-Template",
        )

    for bad in (24, 101):
        try:
            compile_controller_command(
                Path("does-not-matter.jsonl"),
                pid="744DBD59D734",
                module="blower",
                setpoints={"level": bad},
            )
        except SpiderFarmerCommandError:
            pass
        else:
            raise AssertionError(f"Ungültiger Produktions-Blower-Wert akzeptiert: {bad}")
    print("✅ Produktions-Blower blockiert Werte außerhalb 25..100")

    print("✅ Spider Farmer SF.4D.11 Blower-Produktion vollständig erfolgreich")


if __name__ == "__main__":
    main()
