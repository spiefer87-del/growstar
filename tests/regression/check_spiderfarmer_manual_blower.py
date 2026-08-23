#!/usr/bin/env python3
"""Offline regression for SF.4D.9 manual blower hardware-test path."""

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
        setpoints={"modeType": 0, "mOnOff": 1, "maxSpeed": 40},
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
                    "maxSpeed": 40,
                },
            },
        },
        "Blower-Test sendet nur manuellen Modus, EIN und maxSpeed",
    )
    require(
        compiled["diagnostic"] == "candidate_manual_blower",
        "Blower-Pfad bleibt bis zum Hardwaretest ausdrücklich diagnostisch",
    )

    for bad in (-1, 101, 40.5, True):
        try:
            compile_manual_blower_command(
                pid="744DBD59D734",
                setpoints={"modeType": 0, "maxSpeed": bad},
            )
        except SpiderFarmerCommandError:
            pass
        else:
            raise AssertionError(f"Ungültiges maxSpeed akzeptiert: {bad!r}")

    print("✅ Blower begrenzt maxSpeed auf ganzzahlige 0..100")

    proxy = (ROOT / "bridge/spiderfarmer/command_proxy.py").read_text(encoding="utf-8")
    require(
        '"test_controller_manual_blower"' in proxy
        and "compile_manual_blower_command" in proxy,
        "Privater Command-Socket stellt den isolierten Blower-Hardwaretest bereit",
    )

    print("✅ Spider Farmer SF.4D.9 Blower-Diagnosepfad vollständig erfolgreich")


if __name__ == "__main__":
    main()
