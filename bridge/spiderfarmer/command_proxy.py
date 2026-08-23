"""Opt-in command-capable Spider Farmer proxy for Growstar SF.4D.

The original ReadOnlySpiderFarmerProxy remains untouched. This class is selected
only when GROWSTAR_SF_COMMANDS=1 (the SF.4D service template enables it).

Commands arrive exclusively over a private UNIX socket inside the protected
Spider Farmer state directory. No HTTP listener and no second MQTT connection
is created.

SF.4D.4 adds the private diagnostic action test_controller_minimal.

SF.4D.5 adds a second private fan-only diagnostic action,
test_controller_minimal_powered, which sends mOnOff=1 plus exactly one requested
fan setpoint. The normal UI/device path still uses set_controller unchanged.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from .command_model import (
    SpiderFarmerCommandError,
    compile_controller_command,
    compile_manual_fan_command,
    compile_manual_blower_command,
    compile_manual_light_command,
    compile_minimal_controller_command,
    compile_powered_minimal_fan_command,
)
from .mqtt_command import build_publish
from .proxy import ReadOnlySpiderFarmerProxy, _close_writer


_LOG = logging.getLogger("growstar.spiderfarmer.commands")


class CommandSpiderFarmerProxy(ReadOnlySpiderFarmerProxy):
    def __init__(self, *, state_dir, command_socket, **kwargs):
        super().__init__(**kwargs)
        self.state_dir = Path(state_dir).resolve()
        self.capture_path = self.state_dir / "raw_frames.jsonl"
        self.command_socket = Path(command_socket).resolve()
        self._controller_writers = {}
        self._controller_subscriptions = {}

    async def serve_forever(self):
        ssl_context = self.build_server_ssl_context()

        mqtt_server = await asyncio.start_server(
            self.handle_client,
            host=self.listen_host,
            port=self.listen_port,
            ssl=ssl_context,
            ssl_handshake_timeout=12.0,
        )

        try:
            self.command_socket.unlink()
        except FileNotFoundError:
            pass

        command_server = await asyncio.start_unix_server(
            self._handle_command_client,
            path=str(self.command_socket),
        )

        try:
            self.command_socket.chmod(0o600)
        except OSError:
            pass

        _LOG.info(
            "SF.4D Command-Socket bereit: %s",
            self.command_socket,
        )

        async with mqtt_server, command_server:
            await asyncio.gather(
                mqtt_server.serve_forever(),
                command_server.serve_forever(),
            )

    async def handle_client(self, client_reader, client_writer):
        peer = client_writer.get_extra_info("peername")
        session = {"id": None, "subscriptions": []}

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
                self.diagnostics.transport_error(
                    peer,
                    "upstream-connect",
                    exc,
                )
                return

            controller_to_cloud = asyncio.create_task(
                self._command_pump(
                    client_reader,
                    upstream_writer,
                    direction="up",
                    session=session,
                    peer=peer,
                    controller_writer=client_writer,
                )
            )
            cloud_to_controller = asyncio.create_task(
                self._command_pump(
                    upstream_reader,
                    client_writer,
                    direction="down",
                    session=session,
                    peer=peer,
                    controller_writer=client_writer,
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
            session_id = session.get("id")
            if session_id:
                self._controller_writers.pop(session_id, None)
                self._controller_subscriptions.pop(session_id, None)

            self.diagnostics.disconnected(session_id)
            await _close_writer(upstream_writer)
            await _close_writer(client_writer)

    async def _command_pump(
        self,
        reader,
        writer,
        *,
        direction,
        session,
        peer,
        controller_writer,
    ):
        from .mqtt_codec import (
            MQTT_CONNECT,
            MQTT_SUBSCRIBE,
            parse_packets,
        )
        from .proxy import MAX_PARSE_BUFFER_BYTES

        parse_buffer = b""

        while True:
            data = await reader.read(65536)
            if not data:
                return

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
                    previous_id = session.get("id")

                    self._inspect_packet(
                        packet,
                        direction=direction,
                        session=session,
                        peer=peer,
                    )

                    current_id = session.get("id")

                    if (
                        direction == "up"
                        and packet.packet_type == MQTT_CONNECT
                        and current_id
                        and current_id != previous_id
                    ):
                        self._controller_writers[current_id] = controller_writer

                    if (
                        direction == "up"
                        and packet.packet_type == MQTT_SUBSCRIBE
                        and current_id
                    ):
                        topics = {
                            str(topic)
                            for topic in (packet.topics or ())
                        }
                        session["subscriptions"] = sorted(topics)
                        self._controller_subscriptions[current_id] = topics

            except Exception as exc:
                self.diagnostics.parse_error(
                    f"{direction}: {type(exc).__name__}: {exc}"
                )
                parse_buffer = b""

    async def _handle_command_client(self, reader, writer):
        try:
            raw = await asyncio.wait_for(
                reader.readline(),
                timeout=3.0,
            )

            if len(raw) > 65536:
                raise SpiderFarmerCommandError("Command request too large")

            request = json.loads(raw.decode("utf-8"))
            result = await self._dispatch_command(request)

            response = {
                "success": True,
                **result,
            }
        except Exception as exc:
            response = {
                "success": False,
                "error": type(exc).__name__,
                "message": str(exc),
            }

        writer.write(
            json.dumps(
                response,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8") + b"\n"
        )
        await writer.drain()
        await _close_writer(writer)

    async def _dispatch_command(self, request):
        if not isinstance(request, dict):
            raise SpiderFarmerCommandError(
                "Command request must be an object"
            )

        action = str(request.get("action") or "").strip()
        if action not in {
            "set_controller",
            "test_controller_manual_fan",
            "test_controller_manual_blower",
            "test_controller_manual_light",
            "test_controller_minimal",
            "test_controller_minimal_powered",
        }:
            raise SpiderFarmerCommandError(
                "Unsupported command action"
            )

        controller_id = str(
            request.get("controller_id") or ""
        ).strip().lower()

        pid = str(request.get("pid") or "").strip().upper()
        module = str(request.get("module") or "").strip()
        setpoints = request.get("setpoints")

        if not controller_id or not pid or not module:
            raise SpiderFarmerCommandError(
                "controller_id, pid and module are required"
            )

        writer = self._controller_writers.get(controller_id)
        if writer is None or writer.is_closing():
            raise SpiderFarmerCommandError(
                "Spider-Farmer-Controller ist nicht aktiv mit der Bridge verbunden"
            )

        if action == "test_controller_manual_fan":
            if module != "fan":
                raise SpiderFarmerCommandError(
                    "Manueller Fan-Test ist ausschließlich für fan erlaubt"
                )

            compiled = compile_manual_fan_command(
                pid=pid,
                setpoints=setpoints,
            )
        elif action == "test_controller_manual_blower":
            if module != "blower":
                raise SpiderFarmerCommandError(
                    "Manueller Blower-Test ist ausschließlich für blower erlaubt"
                )

            compiled = compile_manual_blower_command(
                pid=pid,
                setpoints=setpoints,
            )
        elif action == "test_controller_manual_light":
            if module != "light":
                raise SpiderFarmerCommandError(
                    "Manueller Licht-Test ist ausschließlich für light erlaubt"
                )

            compiled = compile_manual_light_command(
                pid=pid,
                setpoints=setpoints,
            )
        elif action == "test_controller_minimal_powered":
            if module != "fan":
                raise SpiderFarmerCommandError(
                    "SF.4D.5 Powered-Minimaltest ist ausschließlich für fan erlaubt"
                )

            compiled = compile_powered_minimal_fan_command(
                self.capture_path,
                pid=pid,
                setpoints=setpoints,
            )
        elif action == "test_controller_minimal":
            compiled = compile_minimal_controller_command(
                self.capture_path,
                pid=pid,
                module=module,
                setpoints=setpoints,
            )
        else:
            compiled = compile_controller_command(
                self.capture_path,
                pid=pid,
                module=module,
                setpoints=setpoints,
            )

        topic = compiled["topic"]
        subscriptions = self._controller_subscriptions.get(
            controller_id,
            set(),
        )

        if topic not in subscriptions:
            raise SpiderFarmerCommandError(
                f"Controller hat das beobachtete DOWN-Topic nicht abonniert: {topic}"
            )

        message = json.dumps(
            compiled["payload"],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        packet = build_publish(topic, message)

        writer.write(packet)
        await writer.drain()

        if action == "test_controller_manual_fan":
            _LOG.warning(
                "SF.4D.8 MANUAL FAN TEST sent controller=%s module=%s fields=%s payload=%s",
                controller_id,
                module,
                sorted(compiled["changed_fields"]),
                compiled["payload"],
            )
        elif action == "test_controller_manual_blower":
            _LOG.warning(
                "SF.4D.11 MANUAL BLOWER TEST sent controller=%s module=%s fields=%s payload=%s",
                controller_id,
                module,
                sorted(compiled["changed_fields"]),
                compiled["payload"],
            )
        elif action == "test_controller_manual_light":
            _LOG.warning(
                "SF.4D.12 MANUAL LIGHT TEST sent controller=%s module=%s fields=%s payload=%s",
                controller_id,
                module,
                sorted(compiled["changed_fields"]),
                compiled["payload"],
            )
        elif action == "test_controller_minimal_powered":
            _LOG.warning(
                "SF.4D.5 POWERED MINIMAL TEST sent controller=%s module=%s fields=%s template=%s payload=%s",
                controller_id,
                module,
                sorted(compiled["changed_fields"]),
                compiled.get("observed_at"),
                compiled["payload"],
            )
        elif action == "test_controller_minimal":
            _LOG.warning(
                "SF.4D.4 MINIMAL TEST sent controller=%s module=%s fields=%s template=%s payload=%s",
                controller_id,
                module,
                sorted(compiled["changed_fields"]),
                compiled.get("observed_at"),
                compiled["payload"],
            )
        else:
            _LOG.warning(
                "SF.4D COMMAND sent controller=%s module=%s fields=%s template=%s",
                controller_id,
                module,
                sorted(compiled["changed_fields"]),
                compiled.get("observed_at"),
            )

        return {
            "status": "sent",
            "controller_id": controller_id,
            "pid": pid,
            "module": module,
            "topic": topic,
            "changed_fields": compiled["changed_fields"],
            "template_observed_at": compiled.get("observed_at"),
            "diagnostic": compiled.get("diagnostic"),
            "verified": False,
        }
