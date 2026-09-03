#!/usr/bin/env python3
"""Offline regression for Growstar Spider Farmer canonical read model."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge.spiderfarmer.diagnostics import BridgeDiagnostics
from bridge.spiderfarmer.state_model import (
    apply_publish,
    new_state,
    normalize_config,
    normalize_live_state,
)


SESSION = "744dbd59d734"
UP_TOPIC = "SF/GGS/CB/API/UP/744DBD59D734"
DOWN_TOPIC = "SF/GGS/CB/API/DOWN/744DBD59D734"


def check_live_normalization():
    normalized = normalize_live_state(
        {
            "sensor": {
                "temp": 23.0,
                "humi": 65.8,
                "vpd": 0.96,
                "isDayEnvTarget": 1,
                "isDaySensor": 1,
            },
            "light": {"level": 0},
            "fan": {"modeType": 2, "on": 1, "level": 2},
            "blower": {"modeType": 8, "on": 1, "level": 50},
        }
    )

    assert normalized["sensor"]["temperature_c"] == 23.0
    assert normalized["sensor"]["humidity_percent"] == 65.8
    assert normalized["sensor"]["vpd_kpa"] == 0.96
    assert normalized["light"]["level"] == 0
    assert normalized["light"]["on"] == 0
    assert normalized["fan"] == {
        "mode_type": 2,
        "on": 1,
        "level": 2,
    }
    assert normalized["blower"]["level"] == 50

    print("✅ SF.2 normalisiert Sensor-, Licht-, Fan- und Blower-Livezustand")


def check_fan_config_normalization():
    normalized = normalize_config(
        {
            "keyPath": ["device", "fan"],
            "fan": {
                "modeType": 2,
                "minSpeed": 2,
                "maxSpeed": 8,
                "shakeLevel": 5,
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
        }
    )

    fan = normalized["fan"]

    assert fan["mode_type"] == 2
    assert fan["standby_level"] == 2
    assert fan["run_level"] == 8
    assert fan["oscillation_level"] == 5
    assert fan["natural_wind"] == 1
    assert fan["on"] == 1
    assert fan["level"] == 5
    assert fan["cycle"] == {
        "weekmask": 127,
        "start_time_s": 20100,
        "run_duration_s": 90,
        "off_duration_s": 270,
        "executions": 52,
    }
    assert fan["schedule"][0]["start_time_s"] == 21600
    assert fan["schedule"][0]["end_time_s"] == 82920

    print("✅ SF.2 übernimmt Fan-L8/L2/Oszillation/Natural-Wind/Zyklus vollständig")


def check_state_merge():
    state = new_state()

    changed = apply_publish(
        state,
        SESSION,
        direction="up",
        topic=UP_TOPIC,
        timestamp="2026-08-22T20:08:48Z",
        payload={
            "method": "getDevSta",
            "pid": "744DBD59D734",
            "data": {
                "sensor": {"temp": 23.0, "humi": 65.8, "vpd": 0.96},
                "light": {"level": 0},
                "fan": {"modeType": 2, "on": 1, "level": 2},
                "blower": {"modeType": 8, "on": 1, "level": 50},
            },
        },
    )
    assert changed is True

    changed = apply_publish(
        state,
        SESSION,
        direction="down",
        topic=DOWN_TOPIC,
        timestamp="2026-08-22T20:08:54Z",
        payload={
            "method": "setConfigField",
            "pid": "744DBD59D734",
            "params": {
                "keyPath": ["device", "fan"],
                "fan": {
                    "modeType": 2,
                    "minSpeed": 2,
                    "maxSpeed": 8,
                    "shakeLevel": 5,
                    "natural": 1,
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
        },
    )
    assert changed is True

    controller = state["controllers"][SESSION]

    assert controller["pid"] == "744DBD59D734"
    assert controller["prefix"] == "CB"
    assert controller["live"]["sensor"]["temperature_c"] == 23.0
    assert controller["live"]["fan"]["level"] == 2
    assert controller["config"]["fan"]["run_level"] == 8
    assert controller["config"]["fan"]["oscillation_level"] == 5

    print("✅ SF.2 trennt Livezustand und vollständige Controller-Konfiguration")


def _publish_test_live(diag, sid):
    diag.publish(
        sid,
        direction="up",
        topic=UP_TOPIC,
        message=json.dumps(
            {
                "method": "getDevSta",
                "pid": "744DBD59D734",
                "data": {
                    "sensor": {
                        "temp": 23.5,
                        "humi": 63.5,
                        "vpd": 1.06,
                    },
                    "light": {"on": 1, "level": 30},
                    "fan": {"modeType": 2, "on": 1, "level": 4},
                    "blower": {"modeType": 8, "on": 1, "level": 90},
                },
            }
        ).encode(),
    )


def _publish_test_fan_config(diag, sid):
    diag.publish(
        sid,
        direction="down",
        topic=DOWN_TOPIC,
        message=json.dumps(
            {
                "method": "setConfigField",
                "pid": "744DBD59D734",
                "params": {
                    "keyPath": ["device", "fan"],
                    "fan": {
                        "modeType": 2,
                        "minSpeed": 2,
                        "maxSpeed": 8,
                        "shakeLevel": 5,
                        "natural": 1,
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
            }
        ).encode(),
    )


def check_diagnostics_persistence():
    with tempfile.TemporaryDirectory() as td:
        diag = BridgeDiagnostics(td, max_capture_bytes=300000)
        sid = diag.session_bound(
            "74:4d:bd:59:d7:34",
            ("10.42.77.187", 57258),
        )

        _publish_test_live(diag, sid)
        _publish_test_fan_config(diag, sid)
        diag.flush_growstar_state(force=True)

        path = Path(td) / "spiderfarmer_state.json"
        assert path.exists()

        state = json.loads(path.read_text(encoding="utf-8"))
        controller = state["controllers"][SESSION]

        assert state["read_only"] is True
        assert state["phase"] == "SF.2"
        assert controller["live"]["light"]["level"] == 30
        assert controller["config"]["fan"]["oscillation_level"] == 5
        assert (path.stat().st_mode & 0o777) == 0o600

    print("✅ SF.2 persistiert ausschließlich normalisierten read-only Growstar-State")


def check_timestamped_state_survives_bridge_restart():
    with tempfile.TemporaryDirectory() as td:
        first = BridgeDiagnostics(td, max_capture_bytes=300000)
        sid = first.session_bound(
            "74:4d:bd:59:d7:34",
            ("10.42.77.187", 57258),
        )

        _publish_test_live(first, sid)
        _publish_test_fan_config(first, sid)
        first.flush_growstar_state(force=True)

        first_state = json.loads(
            (Path(td) / "spiderfarmer_state.json").read_text(
                encoding="utf-8"
            )
        )
        assert first_state["controllers"][SESSION]["live"]["fan"]["level"] == 4
        assert (
            first_state["controllers"][SESSION]["config"]["fan"]["run_level"]
            == 8
        )
        persisted_last_seen = first_state["controllers"][SESSION]["last_seen"]

        # Simulated bridge restart: a new BridgeDiagnostics instance is created
        # against the same private state directory.
        restarted = BridgeDiagnostics(td, max_capture_bytes=300000)

        controller = restarted.growstar_state["controllers"][SESSION]

        assert controller["live"]["sensor"]["temperature_c"] == 23.5
        assert controller["live"]["sensor"]["humidity_percent"] == 63.5
        assert controller["live"]["fan"]["level"] == 4
        assert controller["last_seen"] == persisted_last_seen
        assert controller["pid"] == "744DBD59D734"
        assert controller["prefix"] == "CB"

        fan_config = controller["config"]["fan"]
        assert fan_config["standby_level"] == 2
        assert fan_config["run_level"] == 8
        assert fan_config["oscillation_level"] == 5
        assert fan_config["natural_wind"] == 1
        assert fan_config["cycle"]["run_duration_s"] == 90
        assert fan_config["cycle"]["off_duration_s"] == 270

        # Fresh live traffic repopulates live state without deleting the
        # restored configuration.
        sid = restarted.session_bound(
            "74:4d:bd:59:d7:34",
            ("10.42.77.187", 57259),
        )
        _publish_test_live(restarted, sid)
        restarted.flush_growstar_state(force=True)

        after_live = restarted.growstar_state["controllers"][SESSION]
        assert after_live["live"]["fan"]["level"] == 4
        assert after_live["config"]["fan"]["run_level"] == 8
        assert after_live["config"]["fan"]["oscillation_level"] == 5
        assert after_live["last_seen"] is not None

    print(
        "✅ SF.RESTART.1 behält Config und zeitgestempelten Live-State "
        "ohne Frischeverlängerung"
    )


def check_invalid_persisted_state_is_not_trusted():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "spiderfarmer_state.json"
        path.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "phase": "SF.2",
                    "read_only": False,
                    "controllers": {
                        SESSION: {
                            "config": {
                                "fan": {
                                    "run_level": 10,
                                }
                            }
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        diag = BridgeDiagnostics(td)
        assert diag.growstar_state["controllers"] == {}

    print("✅ SF.3B.1 vertraut keinem nicht-read-only Persistenz-State")


def check_no_command_encoder():
    model_text = (ROOT / "bridge/spiderfarmer/state_model.py").read_text(
        encoding="utf-8"
    )
    diagnostics_text = (
        ROOT / "bridge/spiderfarmer/diagnostics.py"
    ).read_text(encoding="utf-8")

    for text, label in (
        (model_text, "state_model.py"),
        (diagnostics_text, "diagnostics.py"),
    ):
        for forbidden in (
            "build_publish",
            "encode_publish",
            "socket.send",
            "writer.write",
            "asyncio.open_connection",
            "setConfigField(",
        ):
            assert forbidden not in text, (label, forbidden)

    print("✅ SF.3B.1 Persistenz-Fix besitzt keinen Netzwerk-/Command-Sendepfad")


def main():
    check_live_normalization()
    check_fan_config_normalization()
    check_state_merge()
    check_diagnostics_persistence()
    check_timestamped_state_survives_bridge_restart()
    check_invalid_persisted_state_is_not_trusted()
    check_no_command_encoder()
    print("✅ Spider Farmer SF.3B.1 Config-Persistenz Regression vollständig erfolgreich")


if __name__ == "__main__":
    main()
