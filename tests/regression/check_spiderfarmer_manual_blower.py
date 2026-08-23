#!/usr/bin/env python3
"""Offline regression for SF.4D.11 confirmed manual blower production path."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge.spiderfarmer.command_model import (
    SpiderFarmerCommandError,
    compile_manual_blower_command,
)


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    compiled = compile_manual_blower_command(
        pid="744DBD59D734",
        setpoints={"modeType": 0, "mOnOff": 1, "mLevel": 40},
    )

    require(
        compiled["topic"] == "SF/GGS/CB/API/DOWN/744DBD59D734",
        "Blower-Test verwendet das bestehende controller-spezifische DOWN-Topic",
    )
    require(
        compiled["payload"] == {
            "method": "setConfigField",
            "params": {
                "keyPath": ["device", "blower"],
                "blower": {
                    "modeType": 0,
                    "mOnOff": 1,
                    "mLevel": 40,
                },
            },
        },
        "Blower-Test sendet nur manuellen Modus, EIN und mLevel",
    )
    require(
        compiled["diagnostic"] == "confirmed_manual_blower",
        "Blower-mLevel-Pfad ist nach Hardwarebestätigung als bestätigt markiert",
    )

    for bad in (24, 101, 40.5, True):
        try:
            compile_manual_blower_command(
                pid="744DBD59D734",
                setpoints={"modeType": 0, "mLevel": bad},
            )
        except SpiderFarmerCommandError:
            pass
        else:
            raise AssertionError(f"Ungültiges mLevel akzeptiert: {bad!r}")

    print("✅ Blower begrenzt mLevel auf ganzzahlige 25..100")

    proxy = (ROOT / "bridge/spiderfarmer/command_proxy.py").read_text(encoding="utf-8")
    require(
        '"test_controller_manual_blower"' in proxy
        and "compile_manual_blower_command" in proxy,
        "Privater Command-Socket stellt den isolierten Blower-Hardwaretest bereit",
    )

    command_model = (ROOT / "bridge/spiderfarmer/command_model.py").read_text(encoding="utf-8")
    require(
        '"blower": {\n        "level": "mLevel"' in command_model,
        "Produktionsmapping verwendet blower.level -> mLevel",
    )

    from tempfile import TemporaryDirectory
    from bridge.spiderfarmer.command_model import compile_controller_command
    with TemporaryDirectory() as tmp:
        missing_capture = Path(tmp) / "missing.jsonl"
        production = compile_controller_command(
            missing_capture,
            pid="744DBD59D734",
            module="blower",
            setpoints={"level": 70},
        )
    require(
        production["payload"]["params"]["blower"] == {
            "modeType": 0,
            "mOnOff": 1,
            "mLevel": 70,
        }
        and production.get("diagnostic") == "confirmed_manual_blower_fallback",
        "Produktionspfad kann den bestätigten Blower auch ohne Capture-Template schreiben",
    )

    print("✅ Spider Farmer SF.4D.11 Blower-Produktionspfad vollständig erfolgreich")


if __name__ == "__main__":
    main()
