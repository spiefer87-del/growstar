#!/usr/bin/env python3
"""Regression for Growstar Spider Farmer SF.2A sensor-source adapter."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import spiderfarmer


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def sample_state(last_seen="2026-08-22T22:20:00Z"):
    return {
        "schema": 1,
        "phase": "SF.2",
        "read_only": True,
        "controllers": {
            "744dbd59d734": {
                "id": "744dbd59d734",
                "pid": "744DBD59D734",
                "prefix": "CB",
                "last_seen": last_seen,
                "live": {
                    "sensor": {
                        "temperature_c": 22.8,
                        "humidity_percent": 66.3,
                        "vpd_kpa": 0.94,
                        "day_environment_target": 1,
                        "day_sensor": 1,
                    },
                    "light": {"level": 0, "on": 0},
                    "fan": {"mode_type": 2, "on": 1, "level": 2},
                    "blower": {"mode_type": 8, "on": 1, "level": 50},
                },
                "config": {},
            }
        },
    }


def main():
    with tempfile.TemporaryDirectory() as td:
        state_path = Path(td) / "spiderfarmer_state.json"
        state_path.write_text(
            json.dumps(sample_state()),
            encoding="utf-8",
        )

        controllers = spiderfarmer.list_controllers(state_path)
        require(
            len(controllers) == 1
            and controllers[0]["id"] == "744dbd59d734",
            "SF.2A liest genau den normalisierten GGS-Controller",
        )

        require(
            controllers[0]["source_id"]
            == "spiderfarmer:744dbd59d734:environment",
            "SF.2A vergibt stabile controller-weite Sensorquellen-ID",
        )

        calls = []

        def fake_update(source_id, **kwargs):
            calls.append((source_id, kwargs))
            return {
                "id": source_id,
                "temperature": kwargs.get("temperature"),
                "humidity": kwargs.get("humidity"),
            }

        spiderfarmer.reset_sync_cache()

        with mock.patch.object(
            spiderfarmer,
            "update_sensor_source",
            side_effect=fake_update,
        ):
            first = spiderfarmer.sync_sensor_sources(
                state_path,
                now=1000.0,
            )

            require(
                len(first["published"]) == 1
                and len(calls) == 1,
                "Erster echter GGS-Sensorstand wird in Growstar veröffentlicht",
            )

            source_id, kwargs = calls[0]

            require(
                kwargs["source_type"] == "spiderfarmer"
                and kwargs["temperature"] == 22.8
                and kwargs["humidity"] == 66.3,
                "Temperatur und Luftfeuchte werden ohne Umrechnung übernommen",
            )

            require(
                kwargs["raw"]["vpd_kpa"] == 0.94
                and "payload" not in kwargs["raw"],
                "Sensorquelle enthält normalisierte Metadaten, aber keinen MQTT-Rohpayload",
            )

            second = spiderfarmer.sync_sensor_sources(
                state_path,
                now=1030.0,
            )

            require(
                not second["published"]
                and len(calls) == 1,
                "Unveränderter Bridge-Zeitstempel wird nicht künstlich frisch gehalten",
            )

            state_path.write_text(
                json.dumps(
                    sample_state(
                        last_seen="2026-08-22T22:20:05Z"
                    )
                ),
                encoding="utf-8",
            )

            third = spiderfarmer.sync_sensor_sources(
                state_path,
                now=1035.0,
            )

            require(
                len(third["published"]) == 1
                and len(calls) == 2,
                "Neuer echter GGS-Zeitstempel aktualisiert die Growstar-Sensorquelle",
            )

        state_path.write_text("{kaputt", encoding="utf-8")

        require(
            spiderfarmer.load_state(state_path)["controllers"] == {},
            "Beschädigter SF-State fällt sicher auf leeren read-only Zustand zurück",
        )

    service_text = (
        ROOT / "services/spiderfarmer.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "socket.",
        "asyncio.open_connection",
        "encode_publish",
        "build_publish",
        "writer.write",
        "setConfigField(",
    ):
        require(
            forbidden not in service_text,
            f"SF.2A Adapter besitzt keinen Command-/Transportpfad: {forbidden}",
        )

    thread_text = (
        ROOT / "threads/hardware.py"
    ).read_text(encoding="utf-8")

    require(
        "sync_sensor_sources()" in thread_text,
        "Bestehender Hardware-Thread integriert den read-only Spider-Farmer-Sync",
    )

    require(
        "HARDWARE_REFRESH_INTERVAL = 30" in thread_text,
        "Bestehender Hardware-Poll-Takt bleibt unverändert",
    )

    print(
        "✅ Spider Farmer SF.2A Growstar-Sensoradapter vollständig erfolgreich"
    )


if __name__ == "__main__":
    main()
