"""Read-only Netzwerkdiagnose für Growstar Phase 4S.

Die erste Network-Management-Stufe verändert bewusst keine Verbindungen.
NetworkManager wird ausschließlich über feste nmcli-Argumentlisten abgefragt.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess


NMCLI_TIMEOUT_SECONDS = 8


def _split_escaped(line):
    """Teilt nmcli -t Ausgabe, ohne escaped Doppelpunkte zu verlieren."""

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


def _run_nmcli(*args):
    executable = shutil.which("nmcli")
    if not executable:
        raise RuntimeError("NetworkManager/nmcli ist nicht verfügbar")

    env = os.environ.copy()
    env["LC_ALL"] = "C"

    try:
        completed = subprocess.run(
            [executable, "--terse", "--escape", "yes", *args],
            capture_output=True,
            text=True,
            timeout=NMCLI_TIMEOUT_SECONDS,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "NetworkManager-Abfrage hat das Zeitlimit überschritten"
        ) from exc

    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "nmcli Fehler").strip()
        raise RuntimeError(message)

    return completed.stdout


def network_manager_available():
    return shutil.which("nmcli") is not None


def _device_ip_details(device):
    result = {
        "addresses": [],
        "gateway": None,
        "dns": [],
    }

    output = _run_nmcli(
        "--fields",
        "IP4.ADDRESS,IP4.GATEWAY,IP4.DNS",
        "device",
        "show",
        device,
    )

    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue
        key, separator, value = raw_line.partition(":")
        if not separator:
            continue
        value = value.replace("\\:", ":").strip()
        if key.startswith("IP4.ADDRESS") and value:
            result["addresses"].append(value)
        elif key.startswith("IP4.GATEWAY") and value and not result["gateway"]:
            result["gateway"] = value
        elif key.startswith("IP4.DNS") and value:
            result["dns"].append(value)

    return result


def network_status():
    """Liefert einen read-only Snapshot der aktuellen NetworkManager-Geräte."""

    available = network_manager_available()
    result = {
        "success": True,
        "read_only": True,
        "manager": "NetworkManager" if available else None,
        "manager_available": available,
        "hostname": socket.gethostname(),
        "online": False,
        "interfaces": [],
        "error": None,
    }

    if not available:
        result["success"] = False
        result["error"] = "NetworkManager/nmcli ist nicht verfügbar"
        return result

    try:
        output = _run_nmcli(
            "--fields",
            "DEVICE,TYPE,STATE,CONNECTION",
            "device",
            "status",
        )

        for raw_line in output.splitlines():
            if not raw_line.strip():
                continue
            parts = _split_escaped(raw_line)
            parts += [""] * (4 - len(parts))
            device, device_type, state, connection = parts[:4]

            item = {
                "device": device,
                "type": device_type,
                "state": state,
                "connection": connection if connection != "--" else None,
                "connected": state == "connected",
                "addresses": [],
                "gateway": None,
                "dns": [],
            }

            if item["connected"]:
                try:
                    item.update(_device_ip_details(device))
                except RuntimeError as exc:
                    item["detail_error"] = str(exc)

            if item["connected"] and device_type in {"ethernet", "wifi"}:
                result["online"] = True

            result["interfaces"].append(item)

    except RuntimeError as exc:
        result["success"] = False
        result["error"] = str(exc)

    return result


def wifi_scan():
    """Scannt sichtbare WLANs read-only und fasst doppelte SSIDs zusammen."""

    result = {
        "success": True,
        "read_only": True,
        "manager_available": network_manager_available(),
        "networks": [],
        "error": None,
    }

    if not result["manager_available"]:
        result["success"] = False
        result["error"] = "NetworkManager/nmcli ist nicht verfügbar"
        return result

    try:
        output = _run_nmcli(
            "--fields",
            "IN-USE,SSID,SIGNAL,SECURITY",
            "device",
            "wifi",
            "list",
            "--rescan",
            "auto",
        )
    except RuntimeError as exc:
        result["success"] = False
        result["error"] = str(exc)
        return result

    by_ssid = {}
    hidden_count = 0

    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue
        parts = _split_escaped(raw_line)
        parts += [""] * (4 - len(parts))
        in_use, ssid, signal, security = parts[:4]

        if not ssid:
            hidden_count += 1
            ssid = f"<verstecktes WLAN {hidden_count}>"

        try:
            signal_value = max(0, min(100, int(signal)))
        except (TypeError, ValueError):
            signal_value = None

        item = {
            "ssid": ssid,
            "signal": signal_value,
            "security": security or "--",
            "connected": in_use.strip() == "*",
        }

        previous = by_ssid.get(ssid)
        previous_signal = previous.get("signal") if previous else None
        if previous is None or (signal_value or -1) > (previous_signal or -1):
            by_ssid[ssid] = item
        elif item["connected"]:
            previous["connected"] = True

    result["networks"] = sorted(
        by_ssid.values(),
        key=lambda item: (
            not item["connected"],
            -(item["signal"] if item["signal"] is not None else -1),
            item["ssid"].lower(),
        ),
    )
    return result
