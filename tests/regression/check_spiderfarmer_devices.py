#!/usr/bin/env python3
"""Regression for Growstar Spider Farmer SF.3A device inventory."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from bridge.spiderfarmer.device_model import build_controller_devices
from services import spiderfarmer


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
                    "blower": {
                        "mode_type": 8,
                        "on": 1,
                        "level": 50,
                    },
                    "outlet": {
                        "channels": {
                            "O1": {
                                "on": 1,
                                "mode_type": 0,
                            },
                        },
                    },
                },
            },
        },
    }


def main():
    controller = sample_state()["controllers"]["744dbd59d734"]

    devices = build_controller_devices(controller)

    by_id = {
        item["id"]: item
        for item in devices
    }

    require(
        "environment" in by_id,
        "SF.3A modelliert den GGS-Umweltsensor als Gerät",
    )

    require(
        "light" in by_id,
        "SF.3A modelliert Licht aus Live-State",
    )

    require(
        "fan" in by_id,
        "SF.3A modelliert Ventilator aus Live- und Config-State",
    )

    require(
        "blower" in by_id,
        "SF.3A modelliert Gebläse aus Live-State",
    )

    fan = by_id["fan"]

    require(
        fan["effective"]["level"] == 2,
        "Ventilator-Live-Level hat Vorrang vor Konfigurationswert",
    )

    require(
        fan["effective"]["run_level"] == 8,
        "Ventilator Run-Level wird normalisiert bereitgestellt",
    )

    require(
        fan["effective"]["standby_level"] == 2,
        "Ventilator Standby-Level wird normalisiert bereitgestellt",
    )

    require(
        fan["effective"]["oscillation_level"] == 5,
        "Ventilator Oszillation/shakeLevel wird als oscillation_level bereitgestellt",
    )

    require(
        fan["effective"]["natural_wind"] == 1,
        "Ventilator Natural-Wind-Konfiguration wird bereitgestellt",
    )

    require(
        fan["effective"]["cycle"] == {
            "weekmask": 127,
            "start_time_s": 20100,
            "run_duration_s": 90,
            "off_duration_s": 270,
            "executions": 52,
        },
        "Ventilator-Zyklus bleibt vollständig normalisiert",
    )

    require(
        "oscillation_level" in fan["capabilities"],
        "Oszillation wird als echte beobachtete Fähigkeit ausgewiesen",
    )

    outlet = by_id["outlet"]

    require(
        len(outlet["channels"]) == 2,
        "Spider-Farmer-Steckdosenkanäle werden einzeln modelliert",
    )

    require(
        outlet["channels"][0]["id"] == "outlet:O1",
        "Outlet-Kanal-IDs sind stabil und kanonisch",
    )

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "spiderfarmer_state.json"

        path.write_text(
            json.dumps(
                sample_state(),
                indent=2,
            ),
            encoding="utf-8",
        )

        controllers = spiderfarmer.list_controllers(path)

        require(
            len(controllers) == 1,
            "Growstar-Adapter liefert einen Spider-Farmer-Controller",
        )

        item = controllers[0]

        require(
            item["device_count"] >= 7,
            "Controller enthält Geräte plus Outlet-Kanäle im Device-Count",
        )

        listed = spiderfarmer.list_devices(
            "744dbd59d734",
            path,
        )

        require(
            any(
                device["id"] == "fan"
                for device in listed
            ),
            "Growstar-Service stellt Device-Inventar controllerbezogen bereit",
        )

        queried = spiderfarmer.device(
            "744dbd59d734",
            "fan",
            path,
        )

        require(
            queried["effective"]["oscillation_level"] == 5,
            "Growstar-Service kann Ventilator samt Oszillation gezielt lesen",
        )

        channel = spiderfarmer.device(
            "744dbd59d734",
            "outlet:O2",
            path,
        )

        require(
            channel["effective"]["on"] == 0,
            "Growstar-Service kann einzelnen Outlet-Kanal gezielt lesen",
        )

        snapshot = spiderfarmer.public_snapshot(path)

        require(
            snapshot["phase"] == "SF.3A"
            and snapshot["read_only"] is True,
            "Public Snapshot meldet SF.3A ausdrücklich read-only",
        )

        require(
            snapshot["source_phase"] == "SF.2",
            "SF.3A hält die zugrunde liegende Bridge-Phase transparent fest",
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
        "bridge/spiderfarmer/device_model.py",
        "services/spiderfarmer.py",
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
        "✅ Spider Farmer SF.3A Geräte- und Konfigurationsmodell vollständig erfolgreich"
    )


if __name__ == "__main__":
    main()
