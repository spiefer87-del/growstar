"""Command-line entry point for Growstar Spider Farmer bridge."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import ssl

from .diagnostics import BridgeDiagnostics
from .proxy import ReadOnlySpiderFarmerProxy


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(__file__).resolve().parent


def _env_bool(name, default):
    value = os.getenv(name)
    if value is None:
        return bool(default)
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return int(default)


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Growstar Spider Farmer TLS/MQTT relay. "
            "Command injection is opt-in through GROWSTAR_SF_COMMANDS=1."
        )
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--listen-host",
        default=os.getenv("GROWSTAR_SF_LISTEN_HOST", "0.0.0.0"),
    )
    parser.add_argument(
        "--listen-port",
        type=int,
        default=_env_int("GROWSTAR_SF_LISTEN_PORT", 18883),
    )
    parser.add_argument(
        "--upstream-host",
        default=os.getenv(
            "GROWSTAR_SF_UPSTREAM_HOST",
            "sf.mqtt.spider-farmer.com",
        ),
    )
    parser.add_argument(
        "--upstream-port",
        type=int,
        default=_env_int("GROWSTAR_SF_UPSTREAM_PORT", 8883),
    )
    parser.add_argument(
        "--state-dir",
        default=os.getenv(
            "GROWSTAR_SF_STATE_DIR",
            str(PROJECT_ROOT / "instance" / "spiderfarmer"),
        ),
    )
    parser.add_argument(
        "--cert-file",
        default=os.getenv(
            "GROWSTAR_SF_CERT_FILE",
            str(PACKAGE_ROOT / "certs" / "server.pem"),
        ),
    )
    parser.add_argument(
        "--key-file",
        default=os.getenv(
            "GROWSTAR_SF_KEY_FILE",
            str(PACKAGE_ROOT / "certs" / "server_key.pem"),
        ),
    )
    parser.add_argument(
        "--upstream-ca-file",
        default=os.getenv(
            "GROWSTAR_SF_UPSTREAM_CA_FILE",
            str(PACKAGE_ROOT / "certs" / "upstream_ca.pem"),
        ),
    )
    parser.add_argument(
        "--max-capture-bytes",
        type=int,
        default=_env_int(
            "GROWSTAR_SF_MAX_CAPTURE_BYTES",
            5 * 1024 * 1024,
        ),
    )
    parser.add_argument(
        "--no-payload-capture",
        action="store_true",
        default=not _env_bool("GROWSTAR_SF_CAPTURE_PAYLOADS", True),
    )
    parser.add_argument(
        "--enable-commands",
        action="store_true",
        default=_env_bool("GROWSTAR_SF_COMMANDS", False),
    )
    parser.add_argument(
        "--command-socket",
        default=os.getenv("GROWSTAR_SF_COMMAND_SOCKET", ""),
    )
    return parser


def validate_configuration(args):
    if not (1 <= int(args.listen_port) <= 65535):
        raise ValueError("Ungültiger Listen-Port")
    if not (1 <= int(args.upstream_port) <= 65535):
        raise ValueError("Ungültiger Upstream-Port")
    if not str(args.upstream_host).strip():
        raise ValueError("Upstream-Host fehlt")

    cert_file = Path(args.cert_file).expanduser().resolve()
    key_file = Path(args.key_file).expanduser().resolve()
    upstream_ca_file = Path(args.upstream_ca_file).expanduser().resolve()
    state_dir = Path(args.state_dir).expanduser().resolve()
    command_socket = (
        Path(args.command_socket).expanduser().resolve()
        if str(args.command_socket or "").strip()
        else state_dir / "command.sock"
    )

    for path, label in (
        (cert_file, "Server-Zertifikat"),
        (key_file, "Server-Key"),
        (upstream_ca_file, "Upstream-CA"),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"{label} fehlt: {path}")

    state_dir.mkdir(parents=True, exist_ok=True)

    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.minimum_version = ssl.TLSVersion.TLSv1_2
    server_context.load_cert_chain(
        certfile=str(cert_file),
        keyfile=str(key_file),
    )

    upstream_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    upstream_context.minimum_version = ssl.TLSVersion.TLSv1_2
    upstream_context.check_hostname = True
    upstream_context.verify_mode = ssl.CERT_REQUIRED
    upstream_context.load_verify_locations(cafile=str(upstream_ca_file))

    commands_enabled = bool(args.enable_commands)

    return {
        "success": True,
        "phase": "SF.4D" if commands_enabled else "SF.1",
        "read_only": not commands_enabled,
        "listen": {
            "host": str(args.listen_host),
            "port": int(args.listen_port),
        },
        "upstream": {
            "host": str(args.upstream_host),
            "port": int(args.upstream_port),
            "certificate_verification": True,
        },
        "state_dir": str(state_dir),
        "capture_payloads": not bool(args.no_payload_capture),
        "command_injection": commands_enabled,
        "command_socket": str(command_socket) if commands_enabled else None,
        "network_changes": False,
    }


async def _run(args):
    configuration = validate_configuration(args)

    diagnostics = BridgeDiagnostics(
        configuration["state_dir"],
        capture_payloads=configuration["capture_payloads"],
        max_capture_bytes=args.max_capture_bytes,
    )

    common = dict(
        listen_host=configuration["listen"]["host"],
        listen_port=configuration["listen"]["port"],
        upstream_host=configuration["upstream"]["host"],
        upstream_port=configuration["upstream"]["port"],
        cert_file=args.cert_file,
        key_file=args.key_file,
        upstream_ca_file=args.upstream_ca_file,
        diagnostics=diagnostics,
    )

    if configuration["command_injection"]:
        from .powerstrip_proxy import PowerStripCommandSpiderFarmerProxy

        proxy = PowerStripCommandSpiderFarmerProxy(
            state_dir=configuration["state_dir"],
            command_socket=configuration["command_socket"],
            **common,
        )
    else:
        proxy = ReadOnlySpiderFarmerProxy(**common)

    await proxy.serve_forever()


def main():
    logging.basicConfig(
        level=os.getenv("GROWSTAR_SF_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = build_parser()
    args = parser.parse_args()

    try:
        configuration = validate_configuration(args)
    except Exception as exc:
        parser.error(str(exc))

    if args.check:
        print(
            json.dumps(
                configuration,
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    try:
        asyncio.run(_run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
