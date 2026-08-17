#!/usr/bin/env python3
"""Privilegierter Growstar-Netzwerk-Helper.

Dieses Programm wird root-eigen unter /usr/local/libexec installiert.
Es akzeptiert ausschließlich JSON über stdin, unterstützt nur explizit
freigegebene Aktionen und verweigert Aufrufe außerhalb von growstar.service.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time


NMCLI_TIMEOUT_SECONDS = 10
WIFI_CONNECT_TIMEOUT_SECONDS = 35
WIFI_VERIFY_TIMEOUT_SECONDS = 12
MAX_REQUEST_BYTES = 16 * 1024


class HelperError(RuntimeError):
    pass


def _json_out(payload, exit_code=0):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    raise SystemExit(exit_code)


def _in_growstar_service():
    try:
        text = open("/proc/self/cgroup", "r", encoding="utf-8").read()
    except OSError:
        return False
    return "growstar.service" in text


def _guard():
    if os.geteuid() != 0:
        raise HelperError("Netzwerk-Helper läuft nicht mit den erwarteten Rechten")
    if not _in_growstar_service():
        raise HelperError(
            "Netzwerk-Helper darf nur aus growstar.service aufgerufen werden"
        )


def _split_escaped(line):
    parts = []
    current = []
    escaped = False
    for char in str(line or ""):
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == ":":
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    if escaped:
        current.append("\\")
    parts.append("".join(current))
    return parts


def _run_nmcli(*args, timeout=NMCLI_TIMEOUT_SECONDS, input_text=None):
    executable = shutil.which("nmcli")
    if not executable:
        raise HelperError("NetworkManager/nmcli ist nicht verfügbar")

    env = os.environ.copy()
    env["LC_ALL"] = "C"

    try:
        completed = subprocess.run(
            [executable, "--terse", "--escape", "yes", *args],
            capture_output=True,
            text=True,
            input=input_text,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise HelperError("NetworkManager-Aktion hat das Zeitlimit überschritten") from exc

    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "nmcli Fehler").strip()
        raise HelperError(message)

    return completed.stdout


def _wifi_device():
    output = _run_nmcli(
        "--fields",
        "DEVICE,TYPE,STATE",
        "device",
        "status",
    )

    fallback = None

    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue
        parts = _split_escaped(raw_line)
        parts += [""] * (3 - len(parts))
        device, device_type, state = parts[:3]
        if device_type != "wifi":
            continue
        if state == "connected":
            return device
        if fallback is None:
            fallback = device

    if fallback:
        return fallback

    raise HelperError("Kein verwaltbares WLAN-Interface gefunden")


def _active_ssid(device):
    output = _run_nmcli(
        "--fields",
        "IN-USE,SSID",
        "device",
        "wifi",
        "list",
        "--rescan",
        "no",
        "ifname",
        device,
    )
    for raw_line in output.splitlines():
        parts = _split_escaped(raw_line)
        parts += [""] * (2 - len(parts))
        in_use, ssid = parts[:2]
        if in_use.strip() == "*" and ssid:
            return ssid
    return None


def _device_snapshot(device):
    connection = _run_nmcli(
        "--get-values",
        "GENERAL.CONNECTION",
        "device",
        "show",
        device,
    ).strip()

    addresses = [
        line.strip()
        for line in _run_nmcli(
            "--get-values",
            "IP4.ADDRESS",
            "device",
            "show",
            device,
        ).splitlines()
        if line.strip()
    ]

    gateway = _run_nmcli(
        "--get-values",
        "IP4.GATEWAY",
        "device",
        "show",
        device,
    ).strip() or None

    return {
        "device": device,
        "connection": connection if connection and connection != "--" else None,
        "ssid": _active_ssid(device),
        "addresses": addresses,
        "gateway": gateway,
    }


def _wait_for_target(ssid, device):
    deadline = time.monotonic() + WIFI_VERIFY_TIMEOUT_SECONDS
    last = None

    while time.monotonic() < deadline:
        try:
            last = _device_snapshot(device)
        except HelperError:
            last = None

        if last and last.get("ssid") == ssid and last.get("addresses"):
            return last

        time.sleep(1.0)

    return last


def _rollback(previous, device):
    if not previous or not previous.get("connection"):
        return {
            "rollback_attempted": False,
            "rollback_success": False,
            "rollback_error": None,
        }

    try:
        _run_nmcli(
            "--wait",
            "25",
            "connection",
            "up",
            "id",
            previous["connection"],
            "ifname",
            device,
            timeout=30,
        )
    except HelperError as exc:
        return {
            "rollback_attempted": True,
            "rollback_success": False,
            "rollback_error": str(exc),
        }

    return {
        "rollback_attempted": True,
        "rollback_success": True,
        "rollback_error": None,
    }


def _probe():
    device = _wifi_device()

    hotspot_ready = False
    try:
        value = _run_nmcli(
            "--get-values",
            "WIFI-PROPERTIES.AP",
            "device",
            "show",
            device,
        ).strip().lower()
        hotspot_ready = value == "yes"
    except HelperError:
        hotspot_ready = False

    return {
        "success": True,
        "write_ready": True,
        "hotspot_ready": hotspot_ready,
        "backend": "privileged-helper",
        "profile_scope": "system",
        "device": device,
    }



def _scan():
    """Fordert einen frischen WLAN-Scan mit Helper-Rechten an."""

    device = _wifi_device()

    _run_nmcli(
        "device",
        "wifi",
        "rescan",
        "ifname",
        device,
        timeout=NMCLI_TIMEOUT_SECONDS,
    )

    return {
        "success": True,
        "device": device,
        "scan_requested": True,
    }

def _connect(payload):
    ssid = str(payload.get("ssid") or "").strip()
    password = "" if payload.get("password") is None else str(payload.get("password"))

    if not ssid:
        raise HelperError("WLAN-Name fehlt")
    if any(char in ssid for char in ("\x00", "\n", "\r")):
        raise HelperError("Ungültiger WLAN-Name")
    if len(ssid.encode("utf-8")) > 32:
        raise HelperError("WLAN-Name ist länger als 32 Byte")
    if any(char in password for char in ("\x00", "\n", "\r")):
        raise HelperError("WLAN-Passwort enthält ungültige Steuerzeichen")
    if len(password) > 128:
        raise HelperError("WLAN-Passwort ist zu lang")

    device = _wifi_device()
    previous = _device_snapshot(device)

    if previous.get("ssid") == ssid and previous.get("addresses"):
        return {
            "success": True,
            "already_connected": True,
            "ssid": ssid,
            "device": device,
            "addresses": previous.get("addresses") or [],
            "gateway": previous.get("gateway"),
            "rollback_attempted": False,
            "rollback_success": False,
            "profile_scope": "system",
        }

    args = [
        "--wait",
        str(WIFI_CONNECT_TIMEOUT_SECONDS),
    ]
    input_text = None

    if password:
        # Secret nur über stdin. Es erscheint niemals in ps/top.
        args.append("--ask")
        input_text = password + "\n"

    args.extend([
        "device",
        "wifi",
        "connect",
        ssid,
        "ifname",
        device,
        # Systemweite Profile sind für ein headless Appliance-System
        # erforderlich, damit Autoconnect bereits beim Boot funktioniert.
        "private",
        "no",
    ])

    try:
        _run_nmcli(
            *args,
            timeout=WIFI_CONNECT_TIMEOUT_SECONDS + 5,
            input_text=input_text,
        )
    except HelperError as exc:
        rollback = _rollback(previous, device)
        return {
            "success": False,
            "error": f"WLAN-Verbindung zu '{ssid}' konnte nicht aktiviert werden: {exc}",
            **rollback,
        }

    verified = _wait_for_target(ssid, device)

    if not (verified and verified.get("ssid") == ssid and verified.get("addresses")):
        rollback = _rollback(previous, device)
        return {
            "success": False,
            "error": (
                f"'{ssid}' wurde nicht mit einer gültigen IPv4-Adresse bestätigt. "
                "Die vorherige Verbindung wird wiederhergestellt."
            ),
            **rollback,
        }

    return {
        "success": True,
        "already_connected": False,
        "ssid": ssid,
        "device": device,
        "connection": verified.get("connection"),
        "addresses": verified.get("addresses") or [],
        "gateway": verified.get("gateway"),
        "rollback_attempted": False,
        "rollback_success": False,
        "profile_scope": "system",
    }


def main():
    try:
        _guard()

        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES:
            raise HelperError("Netzwerk-Anfrage ist zu groß")

        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HelperError("Ungültige Netzwerk-Anfrage") from exc

        if not isinstance(payload, dict):
            raise HelperError("Ungültige Netzwerk-Anfrage")

        action = str(payload.get("action") or "").strip()

        if action == "probe":
            _json_out(_probe())

        if action == "scan":
            _json_out(_scan())

        if action == "connect":
            _json_out(_connect(payload))

        raise HelperError("Nicht unterstützte Netzwerk-Aktion")

    except HelperError as exc:
        _json_out(
            {
                "success": False,
                "error": str(exc),
            },
            exit_code=1,
        )


if __name__ == "__main__":
    main()
