#!/usr/bin/env python3
"""Offline regression for SF.4D.10 manual blower mLevel hardware-test path."""

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
        compiled["diagnostic"] == "candidate_manual_blower_mlevel",
        "Blower-mLevel-Pfad bleibt bis zum Hardwaretest ausdrücklich diagnostisch",
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
        '"blower": {\n        "level": "maxSpeed"' in command_model,
        "Produktionsmapping bleibt bis zur Hardwarebestätigung unverändert",
    )

    print("✅ Spider Farmer SF.4D.10 Blower-mLevel-Diagnosepfad vollständig erfolgreich")


if __name__ == "__main__":
    main()
