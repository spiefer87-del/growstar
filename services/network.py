"""Growstar Network Management.

Phase 4S begann read-only. Phase 4S.2 ergänzte den transaktionalen
WLAN-Wechsel. Phase 4S.3 erzwingt auf Wunsch einen frischen WLAN-Scan und
verwendet für neu angelegte WLAN-Verbindungen bevorzugt private, dem
Growstar-Dienstbenutzer gehörende NetworkManager-Profile. Growstar editiert
keine /etc-Netzwerkdateien und übergibt WLAN-Passwörter nicht als
Prozessargument.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import threading
import time


NMCLI_TIMEOUT_SECONDS = 8
WIFI_SCAN_TIMEOUT_SECONDS = 15
WIFI_CONNECT_TIMEOUT_SECONDS = 35
WIFI_VERIFY_TIMEOUT_SECONDS = 12
NETWORK_HELPER_PATH = "/usr/local/libexec/growstar-network-helper"
FORCED_SCAN_SETTLE_SECONDS = 5.0

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


def _run_network_helper(payload, timeout=50):
    """Ruft den root-eigenen, eng begrenzten Netzwerk-Helper auf."""

    sudo = shutil.which("sudo")

    if not sudo:
        raise RuntimeError("sudo ist für den Netzwerk-Helper nicht verfügbar")

    if not os.path.isfile(NETWORK_HELPER_PATH):
        raise RuntimeError(
            "Growstar-Netzwerk-Helper ist noch nicht installiert"
        )

    try:
        completed = subprocess.run(
            [sudo, "-n", NETWORK_HELPER_PATH],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "Growstar-Netzwerk-Helper hat das Zeitlimit überschritten"
        ) from exc

    data = None

    try:
        data = json.loads((completed.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        data = None

    if completed.returncode != 0:
        message = (
            (data or {}).get("error")
            or (completed.stderr or "").strip()
            or "Growstar-Netzwerk-Helper wurde abgelehnt"
        )
        raise RuntimeError(message)

    if not isinstance(data, dict):
        raise RuntimeError("Ungültige Antwort des Growstar-Netzwerk-Helpers")

    return data


def network_permissions():
    """Prüft den tatsächlich verwendeten privilegierten Netzwerkpfad.

    Read-only NetworkManager-Abfragen laufen weiterhin direkt als Growstar.
    Schreibende Änderungen laufen ausschließlich über den root-eigenen Helper.
    """

    result = {
        "success": True,
        "manager_available": network_manager_available(),
        "write_ready": False,
        "hotspot_ready": False,
        "profile_scope": None,
        "backend": "privileged-helper",
        "checks": {},
        "error": None,
    }

    if not result["manager_available"]:
        result["success"] = False
        result["error"] = "NetworkManager/nmcli ist nicht verfügbar"
        return result

    try:
        probe = _run_network_helper({"action": "probe"}, timeout=12)
    except RuntimeError as exc:
        result["checks"] = {
            "helper_installed": os.path.isfile(NETWORK_HELPER_PATH),
            "helper_authorized": False,
        }
        result["error"] = str(exc)
        return result

    result["write_ready"] = bool(probe.get("write_ready"))
    result["hotspot_ready"] = bool(probe.get("hotspot_ready"))
    result["profile_scope"] = probe.get("profile_scope") or "system"
    result["checks"] = {
        "helper_installed": True,
        "helper_authorized": bool(probe.get("success")),
        "service_guard": bool(probe.get("success")),
    }

    if not result["write_ready"]:
        result["error"] = (
            probe.get("error")
            or "Privilegierter Growstar-Netzwerk-Helper ist nicht bereit"
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


def _parse_wifi_list(output):
    by_ssid = {}
    hidden_count = 0

    for raw_line in str(output or "").splitlines():
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

    return sorted(
        by_ssid.values(),
        key=lambda item: (
            not item["connected"],
            -(item["signal"] if item["signal"] is not None else -1),
            item["ssid"].lower(),
        ),
    )


def _read_wifi_list(device=None, rescan="auto"):
    args = [
        "--fields",
        "IN-USE,SSID,SIGNAL,SECURITY",
        "device",
        "wifi",
        "list",
        "--rescan",
        rescan,
    ]

    if device:
        args.extend(["ifname", device])

    return _parse_wifi_list(
        _run_nmcli(
            *args,
            timeout=WIFI_SCAN_TIMEOUT_SECONDS,
        )
    )


def wifi_scan(force=False):
    """Scannt sichtbare WLANs.

    Bei ``force=True`` wird der Scan zuerst ausdrücklich angefordert. Danach
    wartet Growstar auf den Treiber/NetworkManager und liest erst anschließend
    die fertige AP-Liste mit ``--rescan no``. Dadurch wird kein frühes
    Zwischenergebnis mehr an die Oberfläche ausgeliefert.
    """

    result = {
        "success": True,
        "manager_available": network_manager_available(),
        "rescan": "forced-settled" if force else "auto",
        "networks": [],
        "error": None,
    }

    if not result["manager_available"]:
        result["success"] = False
        result["error"] = "NetworkManager/nmcli ist nicht verfügbar"
        return result

    try:
        if force:
            # Das aktive Anfordern eines WLAN-Scans ist auf dem Raspberry
            # eine privilegierte NetworkManager-Aktion. Der unprivilegierte
            # Gunicorn-Prozess darf weiterhin nur die fertige AP-Liste lesen.
            scan_request = _run_network_helper(
                {"action": "scan"},
                timeout=WIFI_SCAN_TIMEOUT_SECONDS,
            )

            device = scan_request.get("device")
            if not scan_request.get("success") or not device:
                raise RuntimeError(
                    scan_request.get("error")
                    or "WLAN-Scan konnte nicht angefordert werden"
                )

            time.sleep(FORCED_SCAN_SETTLE_SECONDS)

            # Kein zweiter Scan: Nur den vom Helper aktualisierten
            # NetworkManager-Cache auslesen.
            result["networks"] = _read_wifi_list(
                device=device,
                rescan="no",
            )
        else:
            result["networks"] = _read_wifi_list(rescan="auto")

    except RuntimeError as exc:
        result["success"] = False
        result["error"] = str(exc)

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
    scan = wifi_scan(force=True)

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

    Die Web-Anwendung bleibt unprivilegiert. Die eigentliche NetworkManager-
    Mutation und der Rollback laufen ausschließlich im root-eigenen Helper.
    """

    ssid = _validate_ssid(ssid)
    permissions = network_permissions()

    if not permissions.get("write_ready"):
        raise NetworkChangeError(
            permissions.get("error")
            or "Growstar-Netzwerk-Helper ist nicht freigegeben"
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
        try:
            result = _run_network_helper(
                {
                    "action": "connect",
                    "ssid": ssid,
                    "password": secret,
                },
                timeout=WIFI_CONNECT_TIMEOUT_SECONDS + WIFI_VERIFY_TIMEOUT_SECONDS + 20,
            )
        finally:
            # Lokale Referenz so früh wie möglich leeren.
            secret = ""

    if not result.get("success"):
        raise NetworkChangeError(
            result.get("error") or "WLAN-Wechsel fehlgeschlagen",
            rollback_attempted=result.get("rollback_attempted", False),
            rollback_success=result.get("rollback_success", False),
            rollback_error=result.get("rollback_error"),
        )

    return result
