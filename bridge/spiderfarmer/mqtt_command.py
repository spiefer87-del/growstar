"""Minimal MQTT PUBLISH encoder for Spider Farmer SF.4D.

This encoder lives outside mqtt_codec.py on purpose. The historical SF.1
read-only decoder remains unchanged and can still be regression-tested as an
independent transport boundary.

SF.4D emits QoS 0 PUBLISH packets only. The controller already owns the MQTT
session and subscription; Growstar injects a command on that existing local
controller connection.
"""

from __future__ import annotations


def _mqtt_string(value):
    raw = str(value).encode("utf-8")
    if len(raw) > 65535:
        raise ValueError("MQTT string too long")
    return len(raw).to_bytes(2, "big") + raw


def _remaining_length(value):
    value = int(value)
    if value < 0:
        raise ValueError("negative remaining length")

    out = bytearray()

    while True:
        encoded = value % 128
        value //= 128
        if value:
            encoded |= 0x80
        out.append(encoded)
        if not value:
            return bytes(out)


def build_publish(topic, message, *, retain=False):
    """Build one MQTT 3.1.1 QoS-0 PUBLISH packet."""

    topic = str(topic or "").strip()
    if not topic:
        raise ValueError("MQTT topic missing")

    if isinstance(message, str):
        message = message.encode("utf-8")
    elif not isinstance(message, (bytes, bytearray)):
        raise TypeError("MQTT message must be bytes or string")

    body = _mqtt_string(topic) + bytes(message)
    flags = 0x01 if retain else 0x00
    header = bytes([(3 << 4) | flags])

    return header + _remaining_length(len(body)) + body
