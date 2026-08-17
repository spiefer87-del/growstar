"""Growstar Network Management.

Phase 4S begann read-only. Phase 4S.2 ergänzt einen bewusst begrenzten,
transaktionalen WLAN-Wechsel über NetworkManager. Growstar editiert keine
/etc-Netzwerkdateien und übergibt WLAN-Passwörter nicht als Prozessargument.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import threading
import time


NMCLI_TIMEOUT_SECONDS = 8
WIFI_CONNECT_TIMEOUT_SECONDS = 35
WIFI_VERIFY_TIMEOUT_SECONDS = 12

_network_change_lock = threading.Lock()


class NetworkChangeError(RuntimeError):
    """Fehler bei einer schreibenden Netzwerkänderung mit Rollback-Status."""

    def __init__(
        self,
        message,
        *,
        rollback_attempted=False,
        rollback_success=False,
        rollback_error=None,
    ):
        super().__init__(message)
        self.rollback_attempted = bool(rollback_attempted)
        self.rollback_success = bool(rollback_success)
        self.rollback_error = rollback_error

    def as_dict(self):
        return {
            "success": False,
            "error": str(self),
            "rollback_attempted": self.rollback_attempted,
            "rollback_success": self.rollback_success,
            "rollback_error": self.rollback_error,
        }


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


def _unescape_value(value):
    value = str(value or "")
    result = []
    escaped = False

    for char in value:
        if escaped:
            result.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        result.append(char)

    if escaped:
        result.append("\\")
    return "".join(result)


def _run_nmcli(
    *args,
    timeout=NMCLI_TIMEOUT_SECONDS,
    input_text=None,
):
    """Führt nmcli ohne Shell aus.

    ``input_text`` wird nur für interaktive Secret-Abfragen verwendet.
    WLAN-Passwörter erscheinen dadurch nicht in der Prozessargumentliste.
    """

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
            input=input_text,
            timeout=timeout,
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


def network_permissions():
    """Liefert die NetworkManager-Rechte des laufenden Growstar-Prozesses."""

    result = {
        "success": True,
        "manager_available": network_manager_available(),
        "write_ready": False,
        "hotspot_ready": False,
        "permissions": {},
        "error": None,
    }

    if not result["manager_available"]:
        result["success"] = False
        result["error"] = "NetworkManager/nmcli ist nicht verfügbar"
        return result

    try:
        output = _run_nmcli(
            "--fields",
            "PERMISSION,VALUE",
            "general",
            "permissions",
        )
    except RuntimeError as exc:
        result["success"] = False
        result["error"] = str(exc)
        return result

    permissions = {}

    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue

        parts = _split_escaped(raw_line)
        parts += [""] * (2 - len(parts))
        permission, value = parts[:2]

        permission = permission.strip()
        value = value.strip().lower()

        if permission:
            permissions[permission] = value

    result["permissions"] = permissions

    network_control = permissions.get(
        "org.freedesktop.NetworkManager.network-control"
    )
    modify_system = permissions.get(
        "org.freedesktop.NetworkManager.settings.modify.system"
    )
    hotspot_permission = permissions.get(
        "org.freedesktop.NetworkManager.wifi.share.protected"
    )

    result["write_ready"] = (
        network_control == "yes"
        and modify_system == "yes"
    )
    result["hotspot_ready"] = (
        result["write_ready"]
        and hotspot_permission == "yes"
    )

    if not result["write_ready"]:
        if network_control == "auth" or modify_system == "auth":
            result["error"] = (
                "NetworkManager verlangt für Änderungen noch eine "
                "interaktive Systemfreigabe."
            )
        elif network_control == "no" or modify_system == "no":
            result["error"] = (
                "Der Growstar-Dienst besitzt noch keine "
                "NetworkManager-Schreibberechtigung."
            )
        else:
            result["error"] = (
                "NetworkManager-Schreibberechtigung konnte nicht "
                "eindeutig bestätigt werden."
            )

    return result


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

        value = _unescape_value(value).strip()

        if key.startswith("IP4.ADDRESS") and value:
            result["addresses"].append(value)
        elif key.startswith("IP4.GATEWAY") and value and not result["gateway"]:
            result["gateway"] = value
        elif key.startswith("IP4.DNS") and value:
            result["dns"].append(value)

    return result


def network_status():
    """Liefert einen Snapshot der aktuellen NetworkManager-Geräte."""

    available = network_manager_available()

    result = {
        "success": True,
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
    """Scannt sichtbare WLANs und fasst doppelte SSIDs zusammen."""

    result = {
        "success": True,
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
        in_use, raw_ssid, signal, security = parts[:4]

        hidden = not bool(raw_ssid)

        if hidden:
            hidden_count += 1
            ssid = f"<verstecktes WLAN {hidden_count}>"
        else:
            ssid = raw_ssid

        try:
            signal_value = max(0, min(100, int(signal)))
        except (TypeError, ValueError):
            signal_value = None

        item = {
            "ssid": ssid,
            "signal": signal_value,
            "security": security or "--",
            "connected": in_use.strip() == "*",
            "hidden": hidden,
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

    raise RuntimeError("Kein verwaltbares WLAN-Interface gefunden")


def _connection_ssid(connection_name):
    if not connection_name:
        return None

    output = _run_nmcli(
        "--get-values",
        "802-11-wireless.ssid",
        "connection",
        "show",
        connection_name,
    )

    for raw_line in output.splitlines():
        value = _unescape_value(raw_line).strip()
        if value:
            return value

    return None


def _active_wifi_snapshot(device=None):
    status = network_status()

    if not status.get("success"):
        return None

    for item in status.get("interfaces") or []:
        if item.get("type") != "wifi":
            continue
        if device and item.get("device") != device:
            continue
        if not item.get("connected"):
            continue

        snapshot = dict(item)

        try:
            snapshot["ssid"] = _connection_ssid(
                snapshot.get("connection")
            )
        except RuntimeError:
            snapshot["ssid"] = None

        return snapshot

    return None


def _wait_for_target_wifi(ssid, device, timeout=WIFI_VERIFY_TIMEOUT_SECONDS):
    deadline = time.monotonic() + max(1, float(timeout))
    last_snapshot = None

    while time.monotonic() < deadline:
        try:
            snapshot = _active_wifi_snapshot(device=device)
        except RuntimeError:
            snapshot = None

        if snapshot:
            last_snapshot = snapshot
            if (
                snapshot.get("ssid") == ssid
                and snapshot.get("addresses")
            ):
                return snapshot

        time.sleep(1.0)

    return last_snapshot


def _rollback_wifi(previous, device):
    if not previous or not previous.get("connection"):
        return {
            "attempted": False,
            "success": False,
            "error": None,
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
    except RuntimeError as exc:
        return {
            "attempted": True,
            "success": False,
            "error": str(exc),
        }

    return {
        "attempted": True,
        "success": True,
        "error": None,
    }


def _validate_ssid(value):
    ssid = str(value or "").strip()

    if not ssid:
        raise ValueError("Bitte ein WLAN auswählen")

    if any(char in ssid for char in ("\x00", "\n", "\r")):
        raise ValueError("Ungültiger WLAN-Name")

    if len(ssid.encode("utf-8")) > 32:
        raise ValueError("Der WLAN-Name ist länger als 32 Byte")

    return ssid


def _target_network(ssid):
    scan = wifi_scan()

    if not scan.get("success"):
        raise RuntimeError(
            scan.get("error") or "WLAN-Scan ist nicht verfügbar"
        )

    for item in scan.get("networks") or []:
        if item.get("ssid") == ssid and not item.get("hidden"):
            return item

    raise ValueError(
        "Das gewählte WLAN ist aktuell nicht sichtbar. Bitte erneut scannen."
    )


def _password_required(network):
    security = str(network.get("security") or "--").strip().upper()

    if "802.1X" in security:
        raise ValueError(
            "Enterprise-WLAN (802.1X) wird in dieser Ausbaustufe "
            "noch nicht unterstützt."
        )

    if "WEP" in security:
        raise ValueError(
            "WEP-Netze werden aus Sicherheitsgründen nicht unterstützt."
        )

    return security not in {"", "--", "NONE", "OPEN"}


def connect_wifi(ssid, password=None):
    """Wechselt kontrolliert auf ein sichtbares WLAN.

    Bei fehlgeschlagener Aktivierung oder fehlender IPv4-Adresse wird versucht,
    die zuvor aktive WLAN-Verbindung wiederherzustellen.
    """

    ssid = _validate_ssid(ssid)
    permissions = network_permissions()

    if not permissions.get("write_ready"):
        raise NetworkChangeError(
            permissions.get("error")
            or "NetworkManager-Schreibzugriff ist nicht freigegeben"
        )

    target = _target_network(ssid)
    requires_password = _password_required(target)

    secret = "" if password is None else str(password)

    if requires_password:
        if not secret:
            raise ValueError("Bitte das WLAN-Passwort eingeben")
        if any(char in secret for char in ("\x00", "\n", "\r")):
            raise ValueError("Das WLAN-Passwort enthält ungültige Steuerzeichen")
        if len(secret) > 128:
            raise ValueError("Das WLAN-Passwort ist zu lang")
    else:
        secret = ""

    with _network_change_lock:
        device = _wifi_device()
        previous = _active_wifi_snapshot(device=device)

        if previous and previous.get("ssid") == ssid:
            return {
                "success": True,
                "already_connected": True,
                "ssid": ssid,
                "device": device,
                "addresses": previous.get("addresses") or [],
                "gateway": previous.get("gateway"),
                "rollback_attempted": False,
                "rollback_success": False,
            }

        connect_args = [
            "--wait",
            str(WIFI_CONNECT_TIMEOUT_SECONDS),
        ]

        input_text = None

        if requires_password:
            # --ask liest das Secret von stdin. Das Passwort landet dadurch
            # nicht in ps/top oder in der Prozessargumentliste.
            connect_args.append("--ask")
            input_text = secret + "\n"

        connect_args.extend([
            "device",
            "wifi",
            "connect",
            ssid,
            "ifname",
            device,
        ])

        try:
            _run_nmcli(
                *connect_args,
                timeout=WIFI_CONNECT_TIMEOUT_SECONDS + 5,
                input_text=input_text,
            )
        except RuntimeError as exc:
            rollback = _rollback_wifi(previous, device)
            raise NetworkChangeError(
                f"WLAN-Verbindung zu '{ssid}' konnte nicht aktiviert werden: {exc}",
                rollback_attempted=rollback["attempted"],
                rollback_success=rollback["success"],
                rollback_error=rollback["error"],
            ) from exc

        verified = _wait_for_target_wifi(ssid, device)

        if not (
            verified
            and verified.get("ssid") == ssid
            and verified.get("addresses")
        ):
            rollback = _rollback_wifi(previous, device)
            raise NetworkChangeError(
                (
                    f"'{ssid}' wurde nicht mit einer gültigen IPv4-Adresse "
                    "bestätigt. Die vorherige Verbindung wird wiederhergestellt."
                ),
                rollback_attempted=rollback["attempted"],
                rollback_success=rollback["success"],
                rollback_error=rollback["error"],
            )

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
        }
