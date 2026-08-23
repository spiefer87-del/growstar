#!/usr/bin/env python3
"""Offline regression for SF.4D observed-template command path."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge.spiderfarmer.command_model import compile_controller_command
from bridge.spiderfarmer.mqtt_command import build_publish
from bridge.spiderfarmer.mqtt_codec import parse_packets


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def _record(*, ts, max_speed, shake_level=4):
    return {
        "ts": ts,
        "direction": "down",
        "session_id": "744dbd59d734",
        "topic": "SF/GGS/CB/API/DOWN/744DBD59D734",
        "qos": 0,
        "retain": False,
        "payload": {
            "method": "setConfigField",
            "params": {
                "keyPath": ["device", "fan"],
                "fan": {
                    "modeType": 2,
                    "minSpeed": 3,
                    "maxSpeed": max_speed,
                    "shakeLevel": shake_level,
                    "natural": 1,
                    "cycleTime": {
                        "weekmask": 127,
                        "startTime": 20100,
                        "openDur": 90,
                        "closeDur": 270,
                        "times": 52,
                    },
                    "timePeriod": [{
                        "enabled": 1,
                        "weekmask": 127,
                        "startTime": 21600,
                        "endTime": 82920,
                    }],
                },
            },
        },
    }


def main():
    with tempfile.TemporaryDirectory() as td:
        capture = Path(td) / "raw_frames.jsonl"
        initial = _record(ts="2026-08-23T09:00:00Z", max_speed=7)
        original_fan = initial["payload"]["params"]["fan"]

        capture.write_text(json.dumps(initial) + "\n", encoding="utf-8")

        compiled = compile_controller_command(
            capture,
            pid="744DBD59D734",
            module="fan",
            setpoints={"level": 8, "oscillation": 5},
        )

        fan = compiled["payload"]["params"]["fan"]

        require(
            fan["maxSpeed"] == 8,
            "Ventilatorstufe wird ausschließlich auf beobachtetes maxSpeed gemappt",
        )
        require(
            fan["shakeLevel"] == 5,
            "Oszillation wird ausschließlich auf beobachtetes shakeLevel gemappt",
        )
        require(
            fan["minSpeed"] == 3
            and fan["natural"] == 1
            and fan["cycleTime"] == original_fan["cycleTime"]
            and fan["timePeriod"] == original_fan["timePeriod"],
            "Unbekannte bzw. nicht bearbeitete Controller-Konfiguration bleibt exakt erhalten",
        )
        require(
            compiled["payload"]["params"]["keyPath"] == ["device", "fan"],
            "Echt beobachteter keyPath wird unverändert wiederverwendet",
        )
        require(
            compiled["topic"] == "SF/GGS/CB/API/DOWN/744DBD59D734",
            "Echt beobachtetes DOWN-Topic wird unverändert wiederverwendet",
        )

        message = json.dumps(
            compiled["payload"],
            separators=(",", ":"),
        ).encode()
        packet = build_publish(compiled["topic"], message)

        parsed, rest = parse_packets(packet)
        require(
            len(parsed) == 1
            and rest == b""
            and parsed[0].topic == compiled["topic"],
            "SF.4D MQTT-PUBLISH ist mit dem bestehenden Decoder vollständig kompatibel",
        )
        require(
            parsed[0].qos == 0,
            "Growstar injiziert ausschließlich QoS-0-Kommandos ohne fremde PUBACK-Zustände",
        )

        rotated = Path(str(capture) + ".1")
        rotated.write_text(
            json.dumps(_record(ts="2026-08-23T08:30:00Z", max_speed=5)) + "\n",
            encoding="utf-8",
        )
        capture.write_text(
            json.dumps({
                "ts": "2026-08-23T10:00:00Z",
                "direction": "up",
                "session_id": "744dbd59d734",
                "topic": "SF/GGS/CB/API/UP/744DBD59D734",
                "payload": {"method": "getDevSta"},
            }) + "\n",
            encoding="utf-8",
        )

        rotated_compiled = compile_controller_command(
            capture,
            pid="744DBD59D734",
            module="fan",
            setpoints={"level": 6},
        )
        rotated_fan = rotated_compiled["payload"]["params"]["fan"]

        require(
            rotated_fan["maxSpeed"] == 6
            and rotated_fan["shakeLevel"] == 4
            and rotated_compiled["observed_at"] == "2026-08-23T08:30:00Z",
            "SF.4D.2 findet ein echtes Fan-Template auch nach Capture-Rotation in raw_frames.jsonl.1",
        )

        capture.write_text(
            json.dumps(
                _record(
                    ts="2026-08-23T10:05:00Z",
                    max_speed=9,
                    shake_level=6,
                )
            ) + "\n",
            encoding="utf-8",
        )

        current_compiled = compile_controller_command(
            capture,
            pid="744DBD59D734",
            module="fan",
            setpoints={"level": 10},
        )
        current_fan = current_compiled["payload"]["params"]["fan"]

        require(
            current_fan["maxSpeed"] == 10
            and current_fan["shakeLevel"] == 6
            and current_compiled["observed_at"] == "2026-08-23T10:05:00Z",
            "Aktuelle Capture-Datei hat Vorrang vor dem älteren rotierten Template",
        )

    command_proxy = (
        ROOT / "bridge/spiderfarmer/command_proxy.py"
    ).read_text(encoding="utf-8")
    legacy_proxy = (
        ROOT / "bridge/spiderfarmer/proxy.py"
    ).read_text(encoding="utf-8")
    legacy_codec = (
        ROOT / "bridge/spiderfarmer/mqtt_codec.py"
    ).read_text(encoding="utf-8")

    require(
        "setConfigField" not in legacy_proxy
        and "build_publish" not in legacy_proxy,
        "Historische SF.1 ReadOnly-Proxydatei bleibt frei von Command-Vokabular",
    )
    require(
        "build_publish" not in legacy_codec,
        "Historischer SF.1 MQTT-Decoder bleibt weiterhin encoderfrei",
    )
    require(
        "start_unix_server" in command_proxy
        and "asyncio.open_connection" in command_proxy,
        "SF.4D erweitert nur die bestehende Bridge-Sitzung und eröffnet keinen zweiten Controller-MQTT-Client",
    )

    service = (
        ROOT / "install/growstar-spiderfarmer.service.in"
    ).read_text(encoding="utf-8")

    require(
        'GROWSTAR_SF_COMMANDS=1' in service
        and "command.sock" in service,
        "SF.4D-Service aktiviert den privaten lokalen Command-Socket explizit",
    )

    route = (ROOT / "routes/device.py").read_text(encoding="utf-8")
    require(
        "send_controller_setpoints" in route
        and "controller_apply" in route,
        "Bestehender Geräte-Speicherpfad dispatcht gespeicherte Controller-Sollwerte über den Provider-Adapter",
    )

    print("✅ Spider Farmer SF.4D.2 Command-Path Regression vollständig erfolgreich")


if __name__ == "__main__":
    main()
