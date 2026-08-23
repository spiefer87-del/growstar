#!/usr/bin/env python3
"""Offline regression for SF.4D.12 manual light command."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge.spiderfarmer.command_model import (
    SpiderFarmerCommandError,
    compile_manual_light_command,
)


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    compiled = compile_manual_light_command(
        pid="744DBD59D734",
        setpoints={
            "modeType": 0,
            "mOnOff": 1,
            "mLevel": 50,
        },
    )

    require(
        compiled["topic"] == "SF/GGS/CB/API/DOWN/744DBD59D734",
        "Manueller Licht-Test verwendet das stabile DOWN-Topic",
    )
    require(
        compiled["payload"] == {
            "method": "setConfigField",
            "params": {
                "keyPath": ["device", "light"],
                "light": {
                    "modeType": 0,
                    "mOnOff": 1,
                    "mLevel": 50,
                },
            },
        },
        "Manueller Licht-Test sendet exakt modeType=0, mOnOff=1 und mLevel",
    )
    require(
        compiled["changed_fields"] == {
            "modeType": 0,
            "mOnOff": 1,
            "mLevel": 50,
        },
        "Changed-Fields entsprechen dem tatsächlich gesendeten Licht-Block",
    )
    require(
        compiled.get("diagnostic") == "manual_light_mlevel_test",
        "Diagnosepfad ist eindeutig als manueller Licht-mLevel-Test markiert",
    )

    for level in (0, 1, 25, 50, 75, 100):
        compile_manual_light_command(
            pid="744DBD59D734",
            setpoints={
                "modeType": 0,
                "mOnOff": 1,
                "mLevel": level,
            },
        )
    print("✅ Licht-mLevel akzeptiert den zentralen Bereich 0..100")

    for level in (-1, 101, 1.5):
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
    print("✅ Ungültige Licht-mLevel werden blockiert")


if __name__ == "__main__":
    main()
