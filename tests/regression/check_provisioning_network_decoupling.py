#!/usr/bin/env python3
"""Growstar 3.11.0 / SF.1 – Geräte-WLAN bleibt vom Raspberry-Uplink getrennt.

Der Test verändert weder NetworkManager noch WLAN, Bluetooth oder Hardware.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import stat
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


def load(rel, name):
    spec = importlib.util.spec_from_file_location(
        name,
        ROOT / rel,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_store_schema_and_target():
    secrets = load(
        "services/network_secrets.py",
        "growstar_network_secrets_sf1_test",
    )

    with tempfile.TemporaryDirectory() as temp:
        path = (
            Path(temp)
            / "instance"
            / "secrets"
            / "network_credentials.json"
        )
        store = secrets.NetworkCredentialStore(
            path
        )

        # Simuliert die bestehende 3.10.8-Datei ohne Ziel-Metadaten.
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "networks": {
                        "Home-WLAN": {
                            "passphrase": "home-test-secret",
                            "source": "manual_verified",
                            "updated_at": 1,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        require(
            store.get("Home-WLAN")
            == "home-test-secret",
            "Version-1-Secret bleibt nach Schemaerweiterung lesbar",
        )
        require(
            store.provisioning_target()
            is None,
            "Alte Secret-Datei erfindet kein Provisionierungsziel",
        )

        target = store.ensure_provisioning_target(
            "Home-WLAN",
            security="WPA2",
            open_network=False,
            source="legacy_active_wifi_migration",
        )

        require(
            target.get("ssid")
            == "Home-WLAN",
            "Bestehendes Heim-WLAN kann einmalig als Geräte-Ziel fixiert werden",
        )

        store.save(
            "Growstar-SF",
            "anderes-test-secret",
            source="regression",
        )

        require(
            store.provisioning_target().get("ssid")
            == "Home-WLAN",
            "Ein weiteres WLAN-Secret überschreibt das feste Geräte-Ziel nicht",
        )

        raw = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        require(
            raw.get("version") == 2
            and raw.get(
                "provisioning_target",
                {},
            ).get("ssid")
            == "Home-WLAN",
            "Secret-Datei persistiert Schema v2 mit separatem Provisionierungsziel",
        )

        public = store.status(
            "Home-WLAN"
        )

        require(
            "password" not in public
            and "passphrase" not in public,
            "Öffentlicher Zielstatus enthält weiterhin kein WLAN-Secret",
        )

        require(
            stat.S_IMODE(
                path.stat().st_mode
            )
            == 0o600,
            "Erweiterte Secret-Datei bleibt Modus 0600",
        )


def test_network_decoupling():
    network = load(
        "services/network.py",
        "growstar_network_sf1_test",
    )
    secrets = load(
        "services/network_secrets.py",
        "growstar_network_secrets_sf1_runtime",
    )

    with tempfile.TemporaryDirectory() as temp:
        store = secrets.NetworkCredentialStore(
            Path(temp)
            / "network_credentials.json"
        )
        store.save(
            "Home-WLAN",
            "home-test-secret",
            source="manual_verified",
        )

        network.network_secret_store = store
        network._active_wifi_snapshot = (
            lambda device=None: {
                "ssid": "Home-WLAN",
            }
        )
        require(
            network._security_is_open(None) is False,
            "Unbekannte WLAN-Security wird fail-closed nicht als offenes Netz behandelt",
        )

        network._current_wifi_security = (
            lambda ssid: (
                "WPA2"
                if ssid == "Home-WLAN"
                else "WPA2"
            )
        )

        def no_nm_import(_ssid):
            raise AssertionError(
                "NetworkManager darf bei vorhandenem Growstar-Secret nicht gelesen werden"
            )

        network.get_current_wifi_password = (
            no_nm_import
        )

        status = (
            network.network_provisioning_secret_status()
        )

        require(
            status.get(
                "provisioning_target_set"
            )
            is True
            and status.get(
                "provisioning_ssid"
            )
            == "Home-WLAN",
            "3.10.8-Bestand pinnt verifiziertes aktives Heim-WLAN sicher als Geräte-Ziel",
        )

        # Danach übernimmt wlan0 gedanklich den Spider-Farmer-AP.
        network._active_wifi_snapshot = (
            lambda device=None: {
                "ssid": "Growstar-SF",
            }
        )
        network._current_wifi_security = (
            lambda _ssid: "WPA2"
        )

        credentials = (
            network.current_wifi_provisioning_credentials()
        )

        require(
            credentials.get("ssid")
            == "Home-WLAN"
            and credentials.get("password")
            == "home-test-secret"
            and credentials.get(
                "provisioning_target"
            )
            is True,
            "Shelly-Provisionierung bleibt trotz aktivem Growstar-SF-WLAN auf dem Heim-WLAN",
        )

        # Selbst ohne irgendein Raspberry-WLAN muss das feste Ziel erhalten
        # bleiben, weil der Raspberry zukünftig über eth0 uplinken darf.
        network._active_wifi_snapshot = (
            lambda device=None: None
        )

        credentials = (
            network.current_wifi_provisioning_credentials()
        )

        require(
            credentials.get("ssid")
            == "Home-WLAN"
            and credentials.get("password")
            == "home-test-secret",
            "Shelly-Provisionierung funktioniert mit reinem Ethernet-Uplink weiter",
        )


def test_spiderfarmer_port():
    from bridge.spiderfarmer import main as sf_main

    parser = sf_main.build_parser()
    args = parser.parse_args([])

    require(
        args.listen_port == 18883,
        "Spider-Farmer-Bridge nutzt standardmäßig Port 18883 statt Gunicorn-Port 8000",
    )

    service = (
        ROOT
        / "install"
        / "growstar-spiderfarmer.service.in"
    ).read_text(
        encoding="utf-8"
    )
    installer = (
        ROOT
        / "install"
        / "install_spiderfarmer_bridge.sh"
    ).read_text(
        encoding="utf-8"
    )

    require(
        "GROWSTAR_SF_LISTEN_PORT=18883"
        in service
        and "TCP/TLS 18883"
        in installer,
        "Systemd-Vorlage und Installer dokumentieren denselben konfliktfreien SF-Port",
    )


def main():
    test_store_schema_and_target()
    test_network_decoupling()
    test_spiderfarmer_port()
    print(
        "✅ Growstar 3.11.0 / SF.1 Provisionierungsnetz- und Port-Schutz vollständig"
    )


if __name__ == "__main__":
    main()
