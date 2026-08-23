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

from bridge.spiderfarmer.command_model import (
    SpiderFarmerCommandError,
    compile_controller_command,
)
from bridge.spiderfarmer.mqtt_command import build_publish
from bridge.spiderfarmer.mqtt_codec import parse_packets


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def _record(*, ts, m_level, shake_level=4):
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
                    "maxSpeed": 8,
                    "mLevel": m_level,
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


def _level_record(*, ts, module, raw_field, value):
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
                "keyPath": ["device", module],
                module: {
                    raw_field: value,
                },
            },
        },
    }


def main():
    with tempfile.TemporaryDirectory() as td:
        capture = Path(td) / "raw_frames.jsonl"
        initial = _record(ts="2026-08-23T09:00:00Z", m_level=7)

        capture.write_text(json.dumps(initial) + "\n", encoding="utf-8")

        compiled = compile_controller_command(
            capture,
            pid="744DBD59D734",
            module="fan",
            setpoints={"level": 8, "oscillation": 5},
        )

        fan = compiled["payload"]["params"]["fan"]

        require(
            fan == {
                "modeType": 0,
                "mOnOff": 1,
                "mLevel": 8,
                "shakeLevel": 5,
            },
            "Produktionspfad sendet manuellen Fan exakt als modeType=0, mOnOff=1, mLevel und shakeLevel",
        )

        for forbidden in (
            "minSpeed",
            "maxSpeed",
            "natural",
            "cycleTime",
            "timePeriod",
        ):
            require(
                forbidden not in fan,
                f"Produktionspfad sendet fremde Fan-Konfiguration {forbidden} nicht zurück",
            )

        require(
            compiled["changed_fields"] == {
                "modeType": 0,
                "mOnOff": 1,
                "mLevel": 8,
                "shakeLevel": 5,
            },
            "Command-Ergebnis benennt den vollständigen tatsächlich gesendeten manuellen Fan-Block",
        )

        require(
            compiled["payload"]["params"]["keyPath"] == ["device", "fan"],
            "Echt beobachteter keyPath wird unverändert wiederverwendet",
        )
        require(
            compiled["topic"] == "SF/GGS/CB/API/DOWN/744DBD59D734",
            "Echt beobachtetes DOWN-Topic wird unverändert wiederverwendet",
        )

        for bad in (
            {"level": 0},
            {"level": 11},
            {"level": 60},
            {"oscillation": 0},
            {"oscillation": 99},
        ):
            try:
                compile_controller_command(
                    capture,
                    pid="744DBD59D734",
                    module="fan",
                    setpoints=bad,
                )
            except SpiderFarmerCommandError:
                pass
            else:
                raise AssertionError(
                    f"Bridge akzeptierte ungültigen Fan-Sollwert: {bad}"
                )

        print("✅ SF.4D.6 Bridge blockiert Fan-Level/Oszillation außerhalb L1 bis L10")

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
            json.dumps(_record(ts="2026-08-23T08:30:00Z", m_level=5)) + "\n",
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
            rotated_fan == {
                "modeType": 0,
                "mOnOff": 1,
                "mLevel": 6,
            }
            and rotated_compiled["observed_at"] == "2026-08-23T08:30:00Z",
            "Capture-Rotation liefert weiterhin das echte Envelope, ohne alte Fan-Konfiguration zurückzusenden",
        )

        # A newer but unsafe historical manual level must never be reused.
        # The compiler falls back to the older valid one.
        capture.write_text(
            json.dumps(
                _record(
                    ts="2026-08-23T10:05:00Z",
                    m_level=60,
                    shake_level=4,
                )
            ) + "\n",
            encoding="utf-8",
        )

        safe_fallback = compile_controller_command(
            capture,
            pid="744DBD59D734",
            module="fan",
            setpoints={"oscillation": 5},
        )
        safe_fan = safe_fallback["payload"]["params"]["fan"]

        require(
            safe_fan == {
                "modeType": 0,
                "mOnOff": 1,
                "shakeLevel": 5,
            }
            and safe_fallback["observed_at"] == "2026-08-23T08:30:00Z",
            "Ungültiges beobachtetes mLevel wird übersprungen und nicht in den neuen Fan-Block kopiert",
        )

        capture.write_text(
            json.dumps(
                _record(
                    ts="2026-08-23T10:10:00Z",
                    m_level=9,
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
            current_fan == {
                "modeType": 0,
                "mOnOff": 1,
                "mLevel": 10,
            }
            and current_compiled["observed_at"] == "2026-08-23T10:10:00Z",
            "Aktuelles gültiges Capture hat Vorrang, Fan-Schreibblock bleibt trotzdem minimal manuell",
        )

        # The 1..10 rule is fan-specific. Light/blower keep their 0..100 scale.
        for module, raw_field in (("light", "mLevel"), ("blower", "maxSpeed")):
            capture.write_text(
                json.dumps(
                    _level_record(
                        ts="2026-08-23T10:20:00Z",
                        module=module,
                        raw_field=raw_field,
                        value=50,
                    )
                ) + "\n",
                encoding="utf-8",
            )

            level_compiled = compile_controller_command(
                capture,
                pid="744DBD59D734",
                module=module,
                setpoints={"level": 60},
            )

            require(
                level_compiled["payload"]["params"][module][raw_field] == 60,
                f"{module} behält die eigene 0-bis-100-Skala",
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

    print("✅ Spider Farmer SF.4D.6 manueller Command-Path vollständig erfolgreich")


if __name__ == "__main__":
    main()
