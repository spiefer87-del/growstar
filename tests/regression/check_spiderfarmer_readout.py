#!/usr/bin/env python3
"""Regression for Spider Farmer SF.3B real-state readout layer."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from bridge.spiderfarmer.readout import (
    build_readout,
    controller_readout,
    format_readout,
)


def require(condition, message):
    if not condition:
        raise AssertionError(message)

    print("✅", message)


def sample_state():
    return {
        "schema": 1,
        "phase": "SF.2",
        "read_only": True,
        "controllers": {
            "744dbd59d734": {
                "id": "744dbd59d734",
                "pid": "744DBD59D734",
                "prefix": "CB",
                "last_seen": "2026-08-22T22:09:15Z",
                "live": {
                    "sensor": {
                        "temperature_c": 23.0,
                        "humidity_percent": 65.7,
                        "vpd_kpa": 0.96,
                    },
                    "light": {
                        "on": 0,
                        "level": 0,
                    },
                    "fan": {
                        "mode_type": 2,
                        "on": 1,
                        "level": 2,
                    },
                    "blower": {
                        "mode_type": 8,
                        "on": 1,
                        "level": 50,
                    },
                    "outlet": {
                        "ps_mode": 1,
                        "channels": {
                            "O1": {
                                "on": 1,
                                "mode_type": 0,
                            },
                            "O2": {
                                "on": 0,
                                "mode_type": 0,
                            },
                        },
                    },
                },
                "config": {
                    "fan": {
                        "mode_type": 2,
                        "on": 1,
                        "level": 2,
                        "standby_level": 2,
                        "run_level": 8,
                        "oscillation_level": 5,
                        "natural_wind": 1,
                        "cycle": {
                            "weekmask": 127,
                            "start_time_s": 20100,
                            "run_duration_s": 90,
                            "off_duration_s": 270,
                            "executions": 52,
                        },
                    },
                },
            },
        },
    }


def main():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "spiderfarmer_state.json"

        path.write_text(
            json.dumps(
                sample_state(),
                indent=2,
            ),
            encoding="utf-8",
        )

        payload = build_readout(path)

        require(
            payload["phase"] == "SF.3B",
            "SF.3B Readout meldet eigene Diagnosephase",
        )

        require(
            payload["read_only"] is True,
            "SF.3B Readout ist ausdrücklich read-only",
        )

        require(
            payload["controller_count"] == 1,
            "SF.3B Readout erkennt genau einen Testcontroller",
        )

        controller = payload["controllers"][0]

        require(
            controller["id"] == "744dbd59d734",
            "Controller-ID bleibt kanonisch erhalten",
        )

        devices = {
            item["id"]: item
            for item in controller["devices"]
        }

        require(
            devices["fan"]["effective"]["run_level"] == 8,
            "Realitäts-Readout zeigt Ventilator Run-Level",
        )

        require(
            devices["fan"]["effective"]["standby_level"] == 2,
            "Realitäts-Readout zeigt Ventilator Standby-Level",
        )

        require(
            devices["fan"]["effective"]["oscillation_level"] == 5,
            "Realitäts-Readout zeigt Ventilator Oszillation",
        )

        require(
            devices["fan"]["effective"]["natural_wind"] == 1,
            "Realitäts-Readout zeigt Natural Wind",
        )

        require(
            devices["fan"]["effective"]["cycle"]["run_duration_s"] == 90
            and devices["fan"]["effective"]["cycle"]["off_duration_s"] == 270,
            "Realitäts-Readout zeigt den vollständigen Ventilator-Zyklus",
        )

        outlet = devices["outlet"]

        require(
            len(outlet["channels"]) == 2,
            "Realitäts-Readout zeigt beide Outlet-Kanäle",
        )

        one = controller_readout(
            "744DBD59D734",
            path,
        )

        require(
            one is not None
            and one["pid"] == "744DBD59D734",
            "Controller kann auch über PID gezielt gelesen werden",
        )

        text = format_readout(payload)

        require(
            "oscillation_level=5" in text,
            "Telefonfreundliche Ausgabe enthält Oszillationswert",
        )

        require(
            "run_level=8" in text
            and "standby_level=2" in text,
            "Telefonfreundliche Ausgabe enthält Run- und Standby-Level",
        )

    forbidden = (
        "socket.",
        "asyncio.open_connection",
        "paho",
        "publish(",
        "build_publish",
        "writer.write",
        "setConfigField(",
    )

    for relative in (
        "bridge/spiderfarmer/readout.py",
        "bridge/spiderfarmer/readout_cli.py",
    ):
        source = (
            ROOT / relative
        ).read_text(
            encoding="utf-8"
        )

        ast.parse(source)

        for token in forbidden:
            require(
                token not in source,
                f"{relative} besitzt keinen Command-/Transportpfad: {token}",
            )

    print(
        "✅ Spider Farmer SF.3B Controller-Readout vollständig erfolgreich"
    )


if __name__ == "__main__":
    main()
