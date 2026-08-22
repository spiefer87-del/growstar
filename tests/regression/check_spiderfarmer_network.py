#!/usr/bin/env python3
"""Offline regression contract for Growstar Spider Farmer SF.1N networking.

No NetworkManager, nftables, interface or route is mutated by this test.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def ok(message):
    print("✅", message)


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    ok(message)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def load_network_module():
    path = ROOT / "install/growstar_spiderfarmer_network.py"
    spec = importlib.util.spec_from_file_location("growstar_sf_network_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sample_config(module):
    return {
        "schema": 1,
        "ssid": "Growstar-SF",
        "password": "UnitTestOnly123456789",
        "wifi_device": "wlan0",
        "uplink_device": "eth0",
        "connection_name": "Growstar-SF",
        "address": "10.42.77.1/24",
        "channel": 6,
        "bridge_port": 18883,
        "upstream_port": 8883,
        "upstream_host": "sf.mqtt.spider-farmer.com",
    }


def test_preflight_contract(module):
    config = sample_config(module)

    module._require_binary = lambda name: f"/usr/bin/{name}"
    module._device_state = lambda device: "100 (connected)" if device == "eth0" else ""
    module._device_addresses = lambda device: ["192.168.178.97/24"] if device == "eth0" else []
    module._default_route_device = lambda: "eth0"
    module._upstream_route_device = lambda host, port: "eth0"
    module._ap_capable = lambda device: device == "wlan0"
    module._provisioning_guard = lambda project, ap_ssid: {
        "provisioning_ssid": "FRITZ!Box 6660 Cable DD",
        "stored_for_provisioning": True,
    }

    result = module.preflight(config, ROOT)
    require(result["success"] is True, "SF.1N-Preflight akzeptiert den bestätigten Ethernet-/AP-Aufbau")
    require(result["default_route_device"] == "eth0", "Default-Route muss über eth0 laufen")
    require(result["cloud_route_device"] == "eth0", "Spider-Farmer-Cloud muss über eth0 geroutet werden")
    require(result["provisioning_ssid"] == "FRITZ!Box 6660 Cable DD", "Shelly-Geräte-Provisionierungsziel bleibt das Heim-WLAN")

    module._default_route_device = lambda: "wlan0"
    result = module.preflight(config, ROOT)
    require(result["success"] is False, "Preflight blockiert AP-Umschaltung ohne Ethernet-Default-Route")


def test_profile_contract(module):
    config = sample_config(module)
    calls = []
    secret_calls = []

    module._connection_exists = lambda name: False

    class Done:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_nmcli(*args, **kwargs):
        calls.append(tuple(str(value) for value in args))
        return Done()

    module._nmcli = fake_nmcli
    module._set_profile_secret = lambda name, password: secret_calls.append((name, password))
    module._ensure_profile(config)

    flattened = "\n".join(" ".join(call) for call in calls)
    require("802-11-wireless.mode ap" in flattened, "Growstar-SF wird als echtes NetworkManager-AP-Profil angelegt")
    require("802-11-wireless.band bg" in flattened and "802-11-wireless.channel 6" in flattened, "GGS-WLAN bleibt kompatibel auf 2,4 GHz / Kanal 6")
    require("ipv4.method shared" in flattened and "10.42.77.1/24" in flattened, "NetworkManager übernimmt DHCP/DNS/Internetfreigabe im separaten /24")
    require("ipv4.never-default yes" in flattened, "Growstar-SF kann die Ethernet-Default-Route nicht übernehmen")
    require("ipv6.method disabled" in flattened, "GGS-Isolationsnetz bleibt bewusst IPv4-only")
    require(config["password"] not in flattened, "Spider-Farmer-WLAN-Passwort erscheint nicht in nmcli-Prozessargumenten")
    require(secret_calls == [("Growstar-SF", config["password"])], "WPA2-Secret wird ausschließlich über den interaktiven stdin-Pfad gesetzt")


def test_firewall_contract(module):
    rules = module.nft_rules(sample_config(module))
    require('iifname "wlan0" tcp dport 8883 redirect to :18883' in rules, "Nur GGS-TCP/8883 von wlan0 wird zur lokalen Bridge umgeleitet")
    require("192.168.0.0/16" in rules and "172.16.0.0/12" in rules and "10.0.0.0/8" in rules, "Spider-Farmer-WLAN darf nicht in private LAN-Netze weiterleiten")
    require('tcp dport { 53, 18883 } accept' in rules, "Am Raspberry sind vom GGS-WLAN nur DNS und TLS-Bridge freigegeben")
    require("udp dport { 53, 67 } accept" in rules, "DHCP und DNS bleiben für GGS-Clients erreichbar")
    require('iifname "eth0"' not in rules, "Ethernet-Upstream wird von der GGS-Redirect-Regel nicht abgefangen")


def test_install_and_systemd_contract():
    installer = read("install/install_spiderfarmer_network.sh")
    service = read("install/growstar-spiderfarmer-network.service.in")
    bridge_service = read("install/growstar-spiderfarmer.service.in")

    executable_lines = [
        line.strip()
        for line in installer.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    require(
        not any(
            line.startswith("systemctl enable")
            or line.startswith("systemctl start")
            or line.startswith("systemctl restart")
            for line in executable_lines
        ),
        "Netzwerk-Installer startet oder aktiviert den AP niemals automatisch",
    )
    require("secrets.choice" in installer and '"password": password' in installer, "AP-Passwort wird lokal zufällig erzeugt statt ins Repository geschrieben")
    require("credentials" in installer and "nicht fotografieren/senden" in installer, "Installer behandelt AP-Zugangsdaten ausdrücklich als lokales Secret")
    require("ExecStart=/usr/local/libexec/growstar-spiderfarmer-network start" in service, "Root-Netzwerkmutation läuft ausschließlich über einen festen systemd-Helper")
    require("ExecStop=/usr/local/libexec/growstar-spiderfarmer-network stop" in service, "Systemd besitzt einen expliziten AP-/Firewall-Rollbackpfad")
    require("Requires=growstar-spiderfarmer-network.service" in bridge_service, "Read-only Bridge kann nicht vor der isolierten Netzwerkgrenze starten")


def test_no_legacy_network_mutation():
    helper = read("install/growstar_spiderfarmer_network.py")
    for forbidden in (
        "/etc/hosts",
        "dnsmasq.conf",
        "hostapd.conf",
        "iptables",
        "sysctl -w",
        "rm -f /etc/NetworkManager",
    ):
        require(forbidden not in helper, f"SF.1N verwendet keinen Legacy-Netzwerkpfad: {forbidden}")

    require("connection.autoconnect" in helper and '"no"' in helper, "AP-Profil wird bis zur systemd-Aktivierung nicht autonom hochgezogen")
    require("previous_connection" in helper and "_restore_previous" in helper, "Vorherige wlan0-Verbindung wird für Stop/Rollback erhalten")


def test_release_contract():
    release_text = read("core/release.py")
    hardware_test = read("tests/regression/check_hardware_provisioning_wifi.py")
    require('"version": "3.11.1"' in release_text and '"phase": "SF.1N"' in release_text, "Growstar-Release ist auf 3.11.1 / SF.1N angehoben")
    require('== "3.11.1"' in hardware_test and '== "SF.1N"' in hardware_test, "Shelly-Kompatibilitätsregression folgt dem neuen Release statt wieder rot zu werden")
    require('== "3.11.0"' in hardware_test and '"Phase SF.1 bleibt direkt' in hardware_test, "Shelly-Regression schützt die direkte 3.11.0-/SF.1-Historie")


def main():
    for rel in (
        "install/growstar_spiderfarmer_network.py",
        "tests/regression/check_spiderfarmer_network.py",
        "core/release.py",
        "tests/regression/check_hardware_provisioning_wifi.py",
    ):
        ast.parse(read(rel), filename=rel)
        ok("Python-Syntax " + rel)

    module = load_network_module()
    test_preflight_contract(module)
    test_profile_contract(module)
    test_firewall_contract(module)
    test_install_and_systemd_contract()
    test_no_legacy_network_mutation()
    test_release_contract()
    print("✅ Growstar 3.11.1 / SF.1N Netzwerkgrenze vollständig geprüft")


if __name__ == "__main__":
    main()
