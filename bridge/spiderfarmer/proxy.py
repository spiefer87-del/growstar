"""Transparent, read-only Spider Farmer TLS/MQTT relay for Growstar SF.1.

The controller's bytes are forwarded unchanged to the Spider Farmer cloud and
the cloud's bytes are forwarded unchanged back to the controller. Inspection is
best-effort and can never create or inject a packet.

This module intentionally contains no command encoder.
"""

from __future__ import annotations

import asyncio
import logging
import ssl

from .diagnostics import BridgeDiagnostics
from .mqtt_codec import (
    MQTT_CONNECT,
    MQTT_PUBLISH,
    MQTT_SUBSCRIBE,
    parse_packets,
)


_LOG = logging.getLogger("growstar.spiderfarmer")
MAX_PARSE_BUFFER_BYTES = 1024 * 1024


class ReadOnlySpiderFarmerProxy:
    def __init__(
        self,
        *,
        listen_host,
        listen_port,
        upstream_host,
        upstream_port,
        cert_file,
        key_file,
        upstream_ca_file,
        diagnostics: BridgeDiagnostics,
        upstream_connect_timeout=10.0,
    ):
        self.listen_host = str(listen_host)
        self.listen_port = int(listen_port)
        self.upstream_host = str(upstream_host)
        self.upstream_port = int(upstream_port)
        self.cert_file = str(cert_file)
        self.key_file = str(key_file)
        self.upstream_ca_file = str(upstream_ca_file)
        self.diagnostics = diagnostics
        self.upstream_connect_timeout = float(upstream_connect_timeout)
        self._upstream_ssl_context = None

        self.diagnostics.configure(
            listen_host=self.listen_host,
            listen_port=self.listen_port,
            upstream_host=self.upstream_host,
            upstream_port=self.upstream_port,
        )

    def build_server_ssl_context(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(
            certfile=self.cert_file,
            keyfile=self.key_file,
        )
        return context

    def build_upstream_ssl_context(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=self.upstream_ca_file)
        return context

    async def serve_forever(self):
        ssl_context = self.build_server_ssl_context()

        server = await asyncio.start_server(
            self.handle_client,
            host=self.listen_host,
            port=self.listen_port,
            ssl=ssl_context,
            ssl_handshake_timeout=12.0,
        )

        addresses = ", ".join(
            str(sock.getsockname())
            for sock in (server.sockets or [])
        )
        _LOG.info(
            "SF.1 READ-ONLY Bridge bereit auf %s -> %s:%s",
            addresses or f"{self.listen_host}:{self.listen_port}",
            self.upstream_host,
            self.upstream_port,
        )
        _LOG.info(
            "SF.1 sendet keinerlei Growstar-Steuerbefehle; "
            "es werden ausschließlich bestehende Bytes transparent weitergeleitet."
        )

        async with server:
            await server.serve_forever()

    async def handle_client(self, client_reader, client_writer):
        peer = client_writer.get_extra_info("peername")
        session = {"id": None}

        self.diagnostics.connection_opened(peer)
        _LOG.info("Spider-Farmer TLS-Verbindung von %s", peer)

        upstream_writer = None

        try:
            if self._upstream_ssl_context is None:
                self._upstream_ssl_context = self.build_upstream_ssl_context()

            try:
                upstream_reader, upstream_writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        self.upstream_host,
                        self.upstream_port,
                        ssl=self._upstream_ssl_context,
                        server_hostname=self.upstream_host,
                    ),
                    timeout=self.upstream_connect_timeout,
                )
            except Exception as exc:
                # SF.1 emuliert absichtlich keinen lokalen Broker. Kann die reale
                # Cloud nicht sicher erreicht werden, wird keine halbe oder
                # synthetische Gerätesitzung erzeugt.
                self.diagnostics.transport_error(
                    peer,
                    "upstream-connect",
                    exc,
                )
                _LOG.warning(
                    "Spider-Farmer Cloud nicht erreichbar für %s: %s",
                    peer,
                    exc,
                )
                return

            controller_to_cloud = asyncio.create_task(
                self._pump(
                    client_reader,
                    upstream_writer,
                    direction="up",
                    session=session,
                    peer=peer,
                )
            )
            cloud_to_controller = asyncio.create_task(
                self._pump(
                    upstream_reader,
                    client_writer,
                    direction="down",
                    session=session,
                    peer=peer,
                )
            )

            done, pending = await asyncio.wait(
                {controller_to_cloud, cloud_to_controller},
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

            for task in done | pending:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    self.diagnostics.transport_error(
                        peer,
                        "relay-task",
                        exc,
                    )

        finally:
            self.diagnostics.disconnected(session.get("id"))

            await _close_writer(upstream_writer)
            await _close_writer(client_writer)

            _LOG.info(
                "Spider-Farmer Verbindung beendet: peer=%s session=%s",
                peer,
                session.get("id") or "unbekannt",
            )

    async def _pump(self, reader, writer, *, direction, session, peer):
        parse_buffer = b""

        while True:
            data = await reader.read(65536)
            if not data:
                return

            # Relay first. Diagnostic decoding is strictly secondary.
            writer.write(data)
            await writer.drain()

            try:
                parse_buffer += data

                if len(parse_buffer) > MAX_PARSE_BUFFER_BYTES:
                    self.diagnostics.parse_error(
                        f"{direction}: MQTT Parse-Puffer überschritt "
                        f"{MAX_PARSE_BUFFER_BYTES} Byte"
                    )
                    parse_buffer = b""
                    continue

                packets, parse_buffer = parse_packets(parse_buffer)

                for packet in packets:
                    self._inspect_packet(
                        packet,
                        direction=direction,
                        session=session,
                        peer=peer,
                    )

            except Exception as exc:
                # A parser bug must never terminate the transparent relay.
                self.diagnostics.parse_error(
                    f"{direction}: {type(exc).__name__}: {exc}"
                )
                parse_buffer = b""

    def _inspect_packet(self, packet, *, direction, session, peer):
        if (
            direction == "up"
            and packet.packet_type == MQTT_CONNECT
            and packet.client_id
        ):
            session["id"] = self.diagnostics.session_bound(
                packet.client_id,
                peer,
            )
            _LOG.info(
                "GGS MQTT CONNECT: %s",
                session["id"],
            )
            return

        if (
            direction == "up"
            and packet.packet_type == MQTT_SUBSCRIBE
            and packet.topics
        ):
            self.diagnostics.subscriptions(
                session.get("id"),
                packet.topics,
            )
            return

        if packet.packet_type != MQTT_PUBLISH:
            return

        self.diagnostics.publish(
            session.get("id"),
            direction=direction,
            topic=packet.topic,
            message=packet.message or b"",
            qos=packet.qos,
            retain=packet.retain,
        )

        # Compact journal line only. Full JSON is kept in the private JSONL
        # capture, not duplicated into systemd logs.
        _LOG.info(
            "GGS MQTT %s session=%s topic=%s bytes=%s",
            "UP" if direction == "up" else "DOWN",
            session.get("id") or "unbekannt",
            packet.topic or "?",
            len(packet.message or b""),
        )


async def _close_writer(writer):
    if writer is None:
        return

    try:
        writer.close()
    except Exception:
        return

    try:
        await writer.wait_closed()
    except Exception:
        pass
