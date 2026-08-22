"""Minimal MQTT 3.1.1 decoder used by the read-only Spider Farmer relay.

Only CONNECT, PUBLISH and SUBSCRIBE fields needed for diagnostics are decoded.
No packet encoder is provided on purpose: Phase SF.1 must not be able to inject
commands into a controller connection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


MQTT_CONNECT = 1
MQTT_PUBLISH = 3
MQTT_SUBSCRIBE = 8


@dataclass(frozen=True)
class MQTTPacket:
    packet_type: int
    flags: int
    payload: bytes
    topic: Optional[str] = None
    message: Optional[bytes] = None
    qos: int = 0
    retain: bool = False
    packet_id: Optional[int] = None
    client_id: Optional[str] = None
    topics: tuple[str, ...] = ()


class _Incomplete(Exception):
    pass


class _Cursor:
    __slots__ = ("buf", "pos")

    def __init__(self, buf: bytes, pos: int = 0):
        self.buf = buf
        self.pos = pos

    def remaining(self) -> int:
        return len(self.buf) - self.pos

    def u8(self) -> int:
        if self.remaining() < 1:
            raise _Incomplete()
        value = self.buf[self.pos]
        self.pos += 1
        return value

    def u16(self) -> int:
        if self.remaining() < 2:
            raise _Incomplete()
        value = (self.buf[self.pos] << 8) | self.buf[self.pos + 1]
        self.pos += 2
        return value

    def take(self, length: int) -> bytes:
        if length < 0 or self.remaining() < length:
            raise _Incomplete()
        value = self.buf[self.pos:self.pos + length]
        self.pos += length
        return value

    def rest(self) -> bytes:
        value = self.buf[self.pos:]
        self.pos = len(self.buf)
        return value

    def mqtt_string(self) -> str:
        length = self.u16()
        return self.take(length).decode("utf-8", errors="replace")

    def remaining_length(self) -> int:
        multiplier = 1
        value = 0

        for _ in range(4):
            byte = self.u8()
            value += (byte & 0x7F) * multiplier
            if not (byte & 0x80):
                return value
            multiplier *= 128

        raise ValueError("MQTT Remaining Length ist länger als 4 Byte")


def parse_packets(buf: bytes) -> tuple[list[MQTTPacket], bytes]:
    """Return complete MQTT packets plus an incomplete trailing byte sequence."""

    packets: list[MQTTPacket] = []
    cursor = _Cursor(bytes(buf or b""))

    while cursor.remaining() > 0:
        frame_start = cursor.pos

        try:
            header = cursor.u8()
            remaining = cursor.remaining_length()
        except _Incomplete:
            return packets, cursor.buf[frame_start:]
        except ValueError:
            # Malformed byte: drop exactly one byte and attempt to re-sync.
            cursor = _Cursor(cursor.buf, frame_start + 1)
            continue

        if cursor.remaining() < remaining:
            return packets, cursor.buf[frame_start:]

        body = cursor.take(remaining)
        packet = MQTTPacket(
            packet_type=header >> 4,
            flags=header & 0x0F,
            payload=body,
        )

        try:
            if packet.packet_type == MQTT_CONNECT:
                packet = _decode_connect(packet)
            elif packet.packet_type == MQTT_PUBLISH:
                packet = _decode_publish(packet)
            elif packet.packet_type == MQTT_SUBSCRIBE:
                packet = _decode_subscribe(packet)
        except (_Incomplete, ValueError):
            # Keep the packet as a generic control packet. The relay itself is
            # independent from diagnostic parsing and must never be interrupted.
            pass

        packets.append(packet)

    return packets, b""


def _decode_connect(packet: MQTTPacket) -> MQTTPacket:
    cur = _Cursor(packet.payload)
    cur.mqtt_string()  # Protocol name, normally "MQTT".
    cur.u8()           # Protocol level.
    cur.u8()           # Connect flags.
    cur.u16()          # Keepalive.
    client_id = cur.mqtt_string()

    return MQTTPacket(
        packet_type=packet.packet_type,
        flags=packet.flags,
        payload=packet.payload,
        client_id=client_id,
    )


def _decode_publish(packet: MQTTPacket) -> MQTTPacket:
    qos = (packet.flags >> 1) & 0x03
    retain = bool(packet.flags & 0x01)

    cur = _Cursor(packet.payload)
    topic = cur.mqtt_string()
    packet_id = cur.u16() if qos > 0 else None
    message = cur.rest()

    return MQTTPacket(
        packet_type=packet.packet_type,
        flags=packet.flags,
        payload=packet.payload,
        topic=topic,
        message=message,
        qos=qos,
        retain=retain,
        packet_id=packet_id,
    )


def _decode_subscribe(packet: MQTTPacket) -> MQTTPacket:
    cur = _Cursor(packet.payload)
    packet_id = cur.u16()
    topics: list[str] = []

    while cur.remaining() > 0:
        topic = cur.mqtt_string()
        cur.u8()  # Requested QoS.
        topics.append(topic)

    return MQTTPacket(
        packet_type=packet.packet_type,
        flags=packet.flags,
        payload=packet.payload,
        packet_id=packet_id,
        topics=tuple(topics),
    )
