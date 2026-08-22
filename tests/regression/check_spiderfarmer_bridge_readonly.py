#!/usr/bin/env python3
"""Offline regression contract for Growstar Spider Farmer phase SF.1."""

from __future__ import annotations

import json
from pathlib import Path
import struct
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge.spiderfarmer.diagnostics import BridgeDiagnostics
from bridge.spiderfarmer.main import build_parser, validate_configuration
from bridge.spiderfarmer.mqtt_codec import (
    MQTT_CONNECT,
    MQTT_PUBLISH,
    parse_packets,
)


def _mqtt_string(value):
    raw = value.encode("utf-8")
    return len(raw).to_bytes(2, "big") + raw


def _remaining_length(value):
    out = bytearray()
    value = int(value)
    while True:
        encoded = value % 128
        value //= 128
        if value:
            encoded |= 0x80
        out.append(encoded)
        if not value:
            return bytes(out)


def _packet(packet_type, flags, body):
    return bytes([(packet_type << 4) | flags]) + _remaining_length(len(body)) + body


def _connect_packet(client_id):
    body = (
        _mqtt_string("MQTT")
        + bytes([4, 2])
        + struct.pack(">H", 60)
        + _mqtt_string(client_id)
    )
    return _packet(MQTT_CONNECT, 0, body)


def _publish_packet(topic, payload):
    body = _mqtt_string(topic) + payload
    return _packet(MQTT_PUBLISH, 0, body)


def check_codec():
    connect = _connect_packet("AA:BB:CC:DD:EE:FF")
    payload = json.dumps(
        {
            "method": "getDevSta",
            "pid": "AABBCCDDEEFF",
            "data": {
                "sensor": {"temp": 24.5, "humi": 55.0},
                "light": {"mOnOff": 1, "mLevel": 60},
            },
        },
        separators=(",", ":"),
    ).encode()

    publish = _publish_packet(
        "SF/GGS/CB/API/UP/AABBCCDDEEFF",
        payload,
    )

    packets, remainder = parse_packets(connect + publish[:-4])
    assert len(packets) == 1
    assert packets[0].client_id == "AA:BB:CC:DD:EE:FF"
    assert remainder

    packets, remainder = parse_packets(remainder + publish[-4:])
    assert len(packets) == 1
    assert packets[0].topic == "SF/GGS/CB/API/UP/AABBCCDDEEFF"
    assert json.loads(packets[0].message)["data"]["light"]["mLevel"] == 60
    assert remainder == b""

    print("✅ MQTT CONNECT/PUBLISH und Fragmentierung werden read-only dekodiert")


def check_diagnostics():
    with tempfile.TemporaryDirectory() as td:
        diag = BridgeDiagnostics(td, max_capture_bytes=300000)
        diag.configure(
            listen_host="127.0.0.1",
            listen_port=8000,
            upstream_host="sf.mqtt.spider-farmer.com",
            upstream_port=8883,
        )
        sid = diag.session_bound("AA:BB:CC:DD:EE:FF", ("127.0.0.1", 12345))
        diag.publish(
            sid,
            direction="up",
            topic="SF/GGS/CB/API/UP/AABBCCDDEEFF",
            message=json.dumps(
                {
                    "method": "getDevSta",
                    "uid": "diagnostic-only",
                    "data": {
                        "sensor": {"temp": 24.5},
                        "light": {"mLevel": 65},
                    },
                }
            ).encode(),
        )
        diag.publish(
            sid,
            direction="down",
            topic="SF/GGS/CB/API/DOWN/AABBCCDDEEFF",
            message=json.dumps(
                {
                    "method": "exampleAppCommand",
                    "params": {"brightness": 65},
                }
            ).encode(),
        )
        diag.disconnected(sid)

        state_path = Path(td) / "bridge_state.json"
        capture_path = Path(td) / "raw_frames.jsonl"

        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["read_only"] is True
        assert state["sessions"]["aabbccddeeff"]["publishes_up"] == 1
        assert state["sessions"]["aabbccddeeff"]["publishes_down"] == 1
        assert state["sessions"]["aabbccddeeff"]["connected"] is False

        lines = capture_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["payload"]["data"]["light"]["mLevel"] == 65
        assert json.loads(lines[1])["direction"] == "down"

        mode = state_path.stat().st_mode & 0o777
        assert mode == 0o600, oct(mode)

    print("✅ Private SF.1-State-/Rohdiagnose zeichnet UP und DOWN auf")


def check_tls_material():
    parser = build_parser()
    args = parser.parse_args([
        "--state-dir", tempfile.mkdtemp(prefix="growstar-sf1-check-"),
    ])
    result = validate_configuration(args)

    assert result["success"] is True
    assert result["read_only"] is True
    assert result["command_injection"] is False
    assert result["network_changes"] is False
    assert result["upstream"]["certificate_verification"] is True

    print("✅ Device-Zertifikat/Key und verifizierte Upstream-CA sind ladbar")


def check_read_only_contract():
    proxy_text = (ROOT / "bridge/spiderfarmer/proxy.py").read_text(encoding="utf-8")
    codec_text = (ROOT / "bridge/spiderfarmer/mqtt_codec.py").read_text(encoding="utf-8")
    installer_text = (ROOT / "install/install_spiderfarmer_bridge.sh").read_text(
        encoding="utf-8"
    )

    # SF.1 intentionally has no MQTT packet encoder and no GGS command vocabulary.
    for forbidden in (
        "build_publish",
        "setConfigField",
        "setConfigFile",
        "setLight",
        "setOnOff",
        "command_handler",
    ):
        assert forbidden not in proxy_text
        assert forbidden not in codec_text

    # The install step must not silently seize the Raspberry networking stack.
    for forbidden in (
        "nmcli ",
        "iptables",
        "nft ",
        "hostapd",
        "dnsmasq",
        "mosquitto",
        "sysctl -w",
    ):
        assert forbidden not in installer_text

    print("✅ SF.1 besitzt keinen Command-Encoder und verändert kein Netzwerk/Mosquitto")


def main():
    check_codec()
    check_diagnostics()
    check_tls_material()
    check_read_only_contract()
    print("✅ Spider Farmer SF.1 Read-only Regression vollständig erfolgreich")


if __name__ == "__main__":
    main()
