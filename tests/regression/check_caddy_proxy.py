#!/usr/bin/env python3
"""Offline regression contract for Growstar's Caddy Ethernet hotfix."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]


def ok(message):
    print("✅", message)


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    ok(message)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def load_sf_network():
    path = ROOT / "install/growstar_spiderfarmer_network.py"
    spec = importlib.util.spec_from_file_location(
        "growstar_sf_network_caddy_test",
        path,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    caddyfile = read("install/Caddyfile.growstar.in")
    installer = read("install/install_caddy_proxy.sh")

    require(
        ":80 {" in caddyfile,
        "Caddy akzeptiert HTTP unabhängig von einer einzelnen Raspberry-IP",
    )
    require(
        "reverse_proxy 127.0.0.1:8000" in caddyfile,
        "Caddy leitet weiterhin ausschließlich an lokalen Gunicorn weiter",
    )
    require(
        "192.168." not in caddyfile
        and "10.42.77." not in caddyfile,
        "Caddy-Konfiguration enthält keine fest verdrahtete LAN- oder SF-IP",
    )
    require(
        "caddy\" validate --config" not in installer
        and "validate --config" in installer,
        "Installer validiert die neue Caddy-Konfiguration vor dem Austausch",
    )
    require(
        "pre-growstar-anyhost-backup" in installer,
        "Bestehende Caddy-Konfiguration wird beim ersten Umbau gesichert",
    )
    require(
        "rollback" in installer
        and "systemctl reload caddy.service" in installer,
        "Caddy-Reload besitzt einen Rollback auf die vorherige Konfiguration",
    )

    sf = load_sf_network()
    rules = sf.nft_rules(
        {
            "wifi_device": "wlan0",
            "uplink_device": "eth0",
            "bridge_port": 18883,
            "upstream_port": 8883,
        }
    )

    require(
        'tcp dport { 53, 18883 } accept' in rules,
        "Spider-Farmer-Netz erlaubt am Raspberry weiterhin nur DNS und TLS-Bridge",
    )
    require(
        "tcp dport { 53, 80, 18883 }" not in rules
        and "tcp dport 80 accept" not in rules,
        "Growstar-Webport 80 bleibt vom isolierten Growstar-SF-WLAN gesperrt",
    )

    print("✅ Growstar 3.11.1 Caddy-Ethernet-Hotfix vollständig geprüft")


if __name__ == "__main__":
    main()
