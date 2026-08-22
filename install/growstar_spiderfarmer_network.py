#!/usr/bin/env python3
"""Root-owned network boundary for the Growstar Spider Farmer bridge.

Phase SF.1N deliberately keeps the network mutation outside Gunicorn.  This
helper is installed under /usr/local/libexec and is only executed by the
root-owned growstar-spiderfarmer-network.service or explicitly via sudo.

It creates one dedicated 2.4 GHz WPA2 Access Point on wlan0 using a NetworkManager
"shared" profile, keeps eth0 as the required upstream, and redirects only TCP
8883 arriving from the Spider-Farmer WLAN to the local read-only bridge on
18883.  It never edits the existing home-WLAN profile and it can restore the
previous wlan0 connection on stop/rollback.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time


DEFAULT_UPSTREAM_HOST = "sf.mqtt.spider-farmer.com"
DEFAULT_UPSTREAM_PORT = 8883
DEFAULT_BRIDGE_PORT = 18883
DEFAULT_WIFI_DEVICE = "wlan0"
DEFAULT_UPLINK_DEVICE = "eth0"
DEFAULT_CONNECTION_NAME = "Growstar-SF"
DEFAULT_SSID = "Growstar-SF"
DEFAULT_ADDRESS = "10.42.77.1/24"
DEFAULT_CHANNEL = 6
COMMAND_TIMEOUT = 20
START_TIMEOUT = 40

NFT_NAT_TABLE = "growstar_sf_nat"
NFT_GUARD_TABLE = "growstar_sf_guard"


class NetworkError(RuntimeError):
    pass


def _json_out(payload, exit_code=0):
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    raise SystemExit(exit_code)


def _atomic_json(path: Path, payload: dict, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
        os.chmod(path, mode)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _require_root():
    if os.geteuid() != 0:
        raise NetworkError("Spider-Farmer-Netzwerkhilfe muss als root laufen")


def _require_binary(name):
    path = shutil.which(name)
    if not path:
        raise NetworkError(f"Benötigtes Programm fehlt: {name}")
    return path


def _run(command, *, timeout=COMMAND_TIMEOUT, input_text=None, check=True):
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    try:
        completed = subprocess.run(
            list(command),
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise NetworkError(
            f"Befehl hat das Zeitlimit überschritten: {command[0]}"
        ) from exc

    if check and completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "Befehl fehlgeschlagen").strip()
        raise NetworkError(message)

    return completed


def _nmcli(*args, timeout=COMMAND_TIMEOUT, input_text=None, check=True):
    nmcli = _require_binary("nmcli")
    return _run(
        [nmcli, "--terse", "--escape", "yes", *args],
        timeout=timeout,
        input_text=input_text,
        check=check,
    )


def _ip(*args, check=True):
    return _run([_require_binary("ip"), *args], check=check)


def _nft(script=None, *args, check=True):
    nft = _require_binary("nft")
    if script is not None:
        return _run([nft, "-f", "-"], input_text=script, check=check)
    return _run([nft, *args], check=check)


def _validate_interface(value, label):
    value = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,32}", value):
        raise NetworkError(f"Ungültiges {label}")
    return value


def _validate_ssid(value):
    value = str(value or "").strip()
    if not value or len(value.encode("utf-8")) > 32:
        raise NetworkError("Ungültige Spider-Farmer-SSID")
    if any(char in value for char in ("\x00", "\n", "\r")):
        raise NetworkError("Ungültige Spider-Farmer-SSID")
    return value


def _validate_psk(value):
    value = str(value or "")
    if not 8 <= len(value) <= 63:
        raise NetworkError("Spider-Farmer-WLAN-Passwort muss 8 bis 63 Zeichen lang sein")
    if any(char in value for char in ("\x00", "\n", "\r")):
        raise NetworkError("Ungültiges Spider-Farmer-WLAN-Passwort")
    return value


def _validate_address(value):
    value = str(value or "").strip()
    # Deliberately constrained to our dedicated private IPv4 /24.
    if not re.fullmatch(r"10\.42\.\d{1,3}\.1/24", value):
        raise NetworkError("Ungültige Spider-Farmer-AP-Adresse")
    third = int(value.split(".")[2])
    if not 1 <= third <= 254:
        raise NetworkError("Ungültige Spider-Farmer-AP-Adresse")
    return value


def _load_config(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise NetworkError(f"Spider-Farmer-Netzwerkkonfiguration fehlt: {path}") from exc
    except (OSError, ValueError) as exc:
        raise NetworkError("Spider-Farmer-Netzwerkkonfiguration ist ungültig") from exc

    if not isinstance(data, dict):
        raise NetworkError("Spider-Farmer-Netzwerkkonfiguration ist ungültig")

    return {
        "schema": int(data.get("schema") or 1),
        "ssid": _validate_ssid(data.get("ssid") or DEFAULT_SSID),
        "password": _validate_psk(data.get("password")),
        "wifi_device": _validate_interface(
            data.get("wifi_device") or DEFAULT_WIFI_DEVICE,
            "WLAN-Interface",
        ),
        "uplink_device": _validate_interface(
            data.get("uplink_device") or DEFAULT_UPLINK_DEVICE,
            "Uplink-Interface",
        ),
        "connection_name": _validate_ssid(
            data.get("connection_name") or DEFAULT_CONNECTION_NAME
        ),
        "address": _validate_address(data.get("address") or DEFAULT_ADDRESS),
        "channel": int(data.get("channel") or DEFAULT_CHANNEL),
        "bridge_port": int(data.get("bridge_port") or DEFAULT_BRIDGE_PORT),
        "upstream_port": int(data.get("upstream_port") or DEFAULT_UPSTREAM_PORT),
        "upstream_host": str(
            data.get("upstream_host") or DEFAULT_UPSTREAM_HOST
        ).strip(),
    }


def _connection_exists(name):
    completed = _nmcli(
        "--get-values",
        "connection.id",
        "connection",
        "show",
        name,
        check=False,
    )
    return completed.returncode == 0 and completed.stdout.strip() == name


def _device_connection(device):
    completed = _nmcli(
        "--get-values",
        "GENERAL.CONNECTION",
        "device",
        "show",
        device,
        check=False,
    )
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value if value and value != "--" else None


def _device_addresses(device):
    completed = _nmcli(
        "--get-values",
        "IP4.ADDRESS",
        "device",
        "show",
        device,
        check=False,
    )
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _device_state(device):
    completed = _nmcli(
        "--get-values",
        "GENERAL.STATE",
        "device",
        "show",
        device,
        check=False,
    )
    return completed.stdout.strip().lower() if completed.returncode == 0 else ""


def _ap_capable(device):
    completed = _nmcli(
        "--get-values",
        "WIFI-PROPERTIES.AP",
        "device",
        "show",
        device,
        check=False,
    )
    return completed.returncode == 0 and completed.stdout.strip().lower() == "yes"


def _default_route_device():
    completed = _ip("route", "show", "default", check=False)
    for raw in completed.stdout.splitlines():
        parts = raw.split()
        if "dev" in parts:
            pos = parts.index("dev")
            if pos + 1 < len(parts):
                return parts[pos + 1]
    return None


def _upstream_route_device(host, port):
    try:
        infos = socket.getaddrinfo(
            host,
            port,
            socket.AF_INET,
            socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise NetworkError(f"Spider-Farmer-Cloud kann nicht aufgelöst werden: {exc}") from exc

    if not infos:
        raise NetworkError("Spider-Farmer-Cloud liefert keine IPv4-Adresse")

    address = infos[0][4][0]
    completed = _ip("route", "get", address, check=False)
    if completed.returncode != 0:
        raise NetworkError("Route zur Spider-Farmer-Cloud konnte nicht ermittelt werden")

    parts = completed.stdout.split()
    if "dev" not in parts:
        return None
    pos = parts.index("dev")
    return parts[pos + 1] if pos + 1 < len(parts) else None


def _provisioning_guard(project_dir: Path, ap_ssid: str):
    if not project_dir.is_dir():
        raise NetworkError(f"Growstar-Projektverzeichnis fehlt: {project_dir}")

    previous_cwd = Path.cwd()
    inserted = False
    try:
        os.chdir(project_dir)
        if str(project_dir) not in sys.path:
            sys.path.insert(0, str(project_dir))
            inserted = True

        from services.network import network_provisioning_secret_status

        status = network_provisioning_secret_status()
    except Exception as exc:
        raise NetworkError(
            f"Geräte-Provisionierungsziel konnte nicht geprüft werden: {exc}"
        ) from exc
    finally:
        os.chdir(previous_cwd)
        if inserted:
            try:
                sys.path.remove(str(project_dir))
            except ValueError:
                pass

    target = str(status.get("provisioning_ssid") or "").strip()
    target_set = bool(status.get("provisioning_target_set"))
    stored = bool(status.get("stored_for_provisioning"))

    if not target_set or not target:
        raise NetworkError(
            "Kein festes Geräte-Provisionierungs-WLAN gesetzt; Spider-Farmer-AP wird nicht gestartet"
        )
    if not stored:
        raise NetworkError(
            "Für das feste Geräte-Provisionierungs-WLAN fehlt das Growstar-Secret"
        )
    if target == ap_ssid:
        raise NetworkError(
            "Spider-Farmer-SSID darf nicht das Geräte-Provisionierungs-WLAN sein"
        )

    return {
        "provisioning_ssid": target,
        "stored_for_provisioning": True,
    }


def preflight(config, project_dir: Path):
    for binary in ("nmcli", "ip", "nft"):
        _require_binary(binary)

    wifi = config["wifi_device"]
    uplink = config["uplink_device"]

    uplink_state = _device_state(uplink)
    uplink_addresses = _device_addresses(uplink)
    default_route = _default_route_device()
    cloud_route = _upstream_route_device(
        config["upstream_host"],
        config["upstream_port"],
    )
    ap_ready = _ap_capable(wifi)
    provisioning = _provisioning_guard(project_dir, config["ssid"])

    problems = []
    if "connected" not in uplink_state:
        problems.append(f"{uplink} ist nicht verbunden")
    if not uplink_addresses:
        problems.append(f"{uplink} besitzt keine IPv4-Adresse")
    if default_route != uplink:
        problems.append(
            f"Default-Route läuft über {default_route or 'unbekannt'} statt {uplink}"
        )
    if cloud_route != uplink:
        problems.append(
            f"Spider-Farmer-Cloud würde über {cloud_route or 'unbekannt'} statt {uplink} geroutet"
        )
    if not ap_ready:
        problems.append(f"{wifi} meldet keine Access-Point-Fähigkeit")

    return {
        "success": not problems,
        "phase": "SF.1N",
        "read_only_bridge": True,
        "wifi_device": wifi,
        "uplink_device": uplink,
        "uplink_connected": "connected" in uplink_state,
        "uplink_addresses": uplink_addresses,
        "default_route_device": default_route,
        "cloud_route_device": cloud_route,
        "ap_capable": ap_ready,
        "ssid": config["ssid"],
        "address": config["address"],
        "channel": config["channel"],
        "bridge_port": config["bridge_port"],
        "redirect_port": config["upstream_port"],
        **provisioning,
        "problems": problems,
    }


def _set_profile_secret(connection_name, password):
    nmcli = _require_binary("nmcli")
    quoted = shlex.quote(password)
    editor_input = (
        "set wifi-sec.key-mgmt wpa-psk\n"
        f"set wifi-sec.psk {quoted}\n"
        "verify\n"
        "save\n"
        "quit\n"
    )
    try:
        completed = _run(
            [nmcli, "connection", "edit", "id", connection_name],
            timeout=COMMAND_TIMEOUT + 10,
            input_text=editor_input,
            check=False,
        )
    finally:
        editor_input = ""
        quoted = ""

    if completed.returncode != 0:
        raise NetworkError(
            "NetworkManager konnte das Spider-Farmer-WLAN-Passwort nicht speichern"
        )


def _ensure_profile(config):
    name = config["connection_name"]
    wifi = config["wifi_device"]

    if not _connection_exists(name):
        _nmcli(
            "connection",
            "add",
            "type",
            "wifi",
            "ifname",
            wifi,
            "con-name",
            name,
            "ssid",
            config["ssid"],
        )

    _nmcli(
        "connection",
        "modify",
        name,
        "connection.autoconnect",
        "no",
        "connection.interface-name",
        wifi,
        "802-11-wireless.mode",
        "ap",
        "802-11-wireless.band",
        "bg",
        "802-11-wireless.channel",
        str(config["channel"]),
        "802-11-wireless.hidden",
        "no",
        "802-11-wireless-security.key-mgmt",
        "wpa-psk",
        "802-11-wireless-security.proto",
        "rsn",
        "802-11-wireless-security.pairwise",
        "ccmp",
        "802-11-wireless-security.group",
        "ccmp",
        "ipv4.method",
        "shared",
        "ipv4.addresses",
        config["address"],
        "ipv4.never-default",
        "yes",
        "ipv6.method",
        "disabled",
    )

    _set_profile_secret(name, config["password"])


def nft_rules(config):
    wifi = config["wifi_device"]
    upstream_port = int(config["upstream_port"])
    bridge_port = int(config["bridge_port"])

    return f"""delete table ip {NFT_NAT_TABLE}\ndelete table inet {NFT_GUARD_TABLE}\nadd table ip {NFT_NAT_TABLE}\nadd chain ip {NFT_NAT_TABLE} prerouting {{ type nat hook prerouting priority dstnat; policy accept; }}\nadd rule ip {NFT_NAT_TABLE} prerouting iifname \"{wifi}\" tcp dport {upstream_port} redirect to :{bridge_port}\nadd table inet {NFT_GUARD_TABLE}\nadd chain inet {NFT_GUARD_TABLE} input {{ type filter hook input priority -10; policy accept; }}\nadd rule inet {NFT_GUARD_TABLE} input iifname \"{wifi}\" ct state established,related accept\nadd rule inet {NFT_GUARD_TABLE} input iifname \"{wifi}\" udp dport {{ 53, 67 }} accept\nadd rule inet {NFT_GUARD_TABLE} input iifname \"{wifi}\" tcp dport {{ 53, {bridge_port} }} accept\nadd rule inet {NFT_GUARD_TABLE} input iifname \"{wifi}\" ip protocol icmp icmp type echo-request accept\nadd rule inet {NFT_GUARD_TABLE} input iifname \"{wifi}\" reject with icmpx type admin-prohibited\nadd chain inet {NFT_GUARD_TABLE} forward {{ type filter hook forward priority -10; policy accept; }}\nadd rule inet {NFT_GUARD_TABLE} forward iifname \"{wifi}\" ip daddr 10.0.0.0/8 reject with icmp type admin-prohibited\nadd rule inet {NFT_GUARD_TABLE} forward iifname \"{wifi}\" ip daddr 172.16.0.0/12 reject with icmp type admin-prohibited\nadd rule inet {NFT_GUARD_TABLE} forward iifname \"{wifi}\" ip daddr 192.168.0.0/16 reject with icmp type admin-prohibited\n"""


def _delete_firewall():
    _nft(None, "delete", "table", "ip", NFT_NAT_TABLE, check=False)
    _nft(None, "delete", "table", "inet", NFT_GUARD_TABLE, check=False)


def _install_firewall(config):
    # Deleting non-existent tables in a single nft batch would abort the batch,
    # therefore cleanup is done best-effort first and creation is then atomic.
    _delete_firewall()
    script = nft_rules(config)
    # The creation batch intentionally contains no delete commands.
    script = "\n".join(
        line
        for line in script.splitlines()
        if not line.startswith("delete table")
    ) + "\n"
    _nft(script)


def _firewall_active():
    nat = _nft(None, "list", "table", "ip", NFT_NAT_TABLE, check=False)
    guard = _nft(None, "list", "table", "inet", NFT_GUARD_TABLE, check=False)
    return nat.returncode == 0 and guard.returncode == 0


def _load_state(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_state(path: Path, payload):
    payload = dict(payload)
    payload["updated_at"] = int(time.time())
    _atomic_json(path, payload, mode=0o600)


def _restore_previous(config, state):
    previous = str(state.get("previous_connection") or "").strip()
    if not previous or previous == config["connection_name"]:
        return False, None
    if not _connection_exists(previous):
        return False, f"Vorheriges WLAN-Profil existiert nicht mehr: {previous}"

    try:
        _nmcli(
            "--wait",
            "30",
            "connection",
            "up",
            "id",
            previous,
            "ifname",
            config["wifi_device"],
            timeout=35,
        )
        return True, None
    except NetworkError as exc:
        return False, str(exc)


def start(config, project_dir: Path, state_path: Path):
    check = preflight(config, project_dir)
    if not check["success"]:
        raise NetworkError("; ".join(check["problems"]))

    state = _load_state(state_path)
    current = _device_connection(config["wifi_device"])

    if current and current != config["connection_name"]:
        state["previous_connection"] = current

    state.update(
        {
            "schema": 1,
            "active": False,
            "wifi_device": config["wifi_device"],
            "uplink_device": config["uplink_device"],
            "ssid": config["ssid"],
            "connection_name": config["connection_name"],
            "address": config["address"],
            "bridge_port": config["bridge_port"],
            "redirect_port": config["upstream_port"],
        }
    )
    _write_state(state_path, state)

    try:
        _ensure_profile(config)
        _nmcli(
            "--wait",
            "35",
            "connection",
            "up",
            "id",
            config["connection_name"],
            "ifname",
            config["wifi_device"],
            timeout=START_TIMEOUT,
        )

        current = _device_connection(config["wifi_device"])
        addresses = _device_addresses(config["wifi_device"])
        if current != config["connection_name"]:
            raise NetworkError("Spider-Farmer-Access-Point wurde nicht als aktive Verbindung bestätigt")
        if config["address"] not in addresses:
            raise NetworkError(
                "Spider-Farmer-Access-Point besitzt nicht die erwartete IPv4-Adresse"
            )

        _install_firewall(config)
        if not _firewall_active():
            raise NetworkError("Spider-Farmer-Firewall/Redirect konnte nicht bestätigt werden")

        state.update(
            {
                "active": True,
                "started_at": int(time.time()),
                "addresses": addresses,
                "provisioning_ssid": check["provisioning_ssid"],
            }
        )
        _write_state(state_path, state)

        return {
            "success": True,
            "active": True,
            "ssid": config["ssid"],
            "wifi_device": config["wifi_device"],
            "uplink_device": config["uplink_device"],
            "addresses": addresses,
            "bridge_port": config["bridge_port"],
            "redirect_port": config["upstream_port"],
            "provisioning_ssid": check["provisioning_ssid"],
        }

    except Exception:
        _delete_firewall()
        _nmcli(
            "connection",
            "down",
            "id",
            config["connection_name"],
            check=False,
        )
        restored, restore_error = _restore_previous(config, state)
        state.update(
            {
                "active": False,
                "rollback_attempted": True,
                "rollback_restored_previous": restored,
                "rollback_error": restore_error,
            }
        )
        _write_state(state_path, state)
        raise


def stop(config, state_path: Path):
    state = _load_state(state_path)
    _delete_firewall()
    _nmcli(
        "connection",
        "down",
        "id",
        config["connection_name"],
        check=False,
    )

    restored, restore_error = _restore_previous(config, state)
    state.update(
        {
            "active": False,
            "stopped_at": int(time.time()),
            "previous_restored": restored,
            "restore_error": restore_error,
        }
    )
    _write_state(state_path, state)

    return {
        "success": restore_error is None,
        "active": False,
        "previous_restored": restored,
        "restore_error": restore_error,
    }


def status(config, state_path: Path):
    state = _load_state(state_path)
    current = _device_connection(config["wifi_device"])
    addresses = _device_addresses(config["wifi_device"])
    firewall = _firewall_active()
    active = (
        current == config["connection_name"]
        and config["address"] in addresses
        and firewall
    )

    return {
        "success": True,
        "active": active,
        "ssid": config["ssid"],
        "connection": current,
        "wifi_device": config["wifi_device"],
        "uplink_device": config["uplink_device"],
        "addresses": addresses,
        "firewall_active": firewall,
        "bridge_port": config["bridge_port"],
        "redirect_port": config["upstream_port"],
        "previous_connection": state.get("previous_connection"),
    }


def show_credentials(config):
    return {
        "success": True,
        "ssid": config["ssid"],
        "password": config["password"],
        "warning": "Diese Zugangsdaten nicht in Screenshots oder Logs veröffentlichen.",
    }


def build_parser():
    parser = argparse.ArgumentParser(
        description="Growstar Spider Farmer Netzwerkgrenze SF.1N"
    )
    parser.add_argument(
        "action",
        choices=("preflight", "start", "stop", "status", "credentials"),
    )
    parser.add_argument(
        "--config",
        default=os.getenv(
            "GROWSTAR_SF_NETWORK_CONFIG",
            "/etc/growstar/spiderfarmer-network.json",
        ),
    )
    parser.add_argument(
        "--state",
        default=os.getenv(
            "GROWSTAR_SF_NETWORK_STATE",
            "/run/growstar-spiderfarmer-network.json",
        ),
    )
    parser.add_argument(
        "--project-dir",
        default=os.getenv("GROWSTAR_PROJECT_DIR", "/home/pi/growstar"),
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        _require_root()
        config = _load_config(Path(args.config).resolve())
        state_path = Path(args.state).resolve()
        project_dir = Path(args.project_dir).resolve()

        if args.action == "preflight":
            result = preflight(config, project_dir)
            _json_out(result, 0 if result["success"] else 1)
        if args.action == "start":
            _json_out(start(config, project_dir, state_path))
        if args.action == "stop":
            result = stop(config, state_path)
            _json_out(result, 0 if result["success"] else 1)
        if args.action == "status":
            _json_out(status(config, state_path))
        if args.action == "credentials":
            _json_out(show_credentials(config))

        raise NetworkError("Nicht unterstützte Aktion")

    except NetworkError as exc:
        _json_out({"success": False, "error": str(exc)}, 1)


if __name__ == "__main__":
    main()
