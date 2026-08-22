#!/usr/bin/env python3
"""Growstar 3.10.6 / Phase 4W.6 – zentraler WLAN-Secret-Store.

Keine echte WLAN-, BLE- oder Hardware-Mutation.
"""

from __future__ import annotations

from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import os
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


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_secret_store():
    module = load(
        "services/network_secrets.py",
        "growstar_network_secrets_4w6_test",
    )

    with tempfile.TemporaryDirectory() as temp:
        path = (
            Path(temp)
            / "instance"
            / "secrets"
            / "network_credentials.json"
        )

        store = module.NetworkCredentialStore(path)

        status = store.save(
            "Growstar-Test",
            "nur-test-passphrase",
            source="regression",
        )

        require(
            status.get("stored_for_active") is True
            and status.get("active_ssid") == "Growstar-Test",
            "Secret-Store meldet das aktive Test-WLAN als gespeichert",
        )

        require(
            "passphrase" not in status
            and "password" not in status,
            "Öffentlicher Secret-Status enthält keine Passphrase",
        )

        require(
            store.get("Growstar-Test") == "nur-test-passphrase",
            "Serverinterner Secret-Leseweg liefert die gespeicherte Passphrase",
        )

        file_mode = stat.S_IMODE(path.stat().st_mode)
        dir_mode = stat.S_IMODE(path.parent.stat().st_mode)
        lock_mode = stat.S_IMODE(
            path.with_suffix(path.suffix + ".lock").stat().st_mode
        )

        require(
            file_mode == 0o600,
            "Secret-Datei besitzt Dateimodus 0600",
        )
        require(
            dir_mode == 0o700,
            "Secret-Verzeichnis besitzt Dateimodus 0700",
        )
        require(
            lock_mode == 0o600,
            "Secret-Lockdatei besitzt Dateimodus 0600",
        )

        raw = json.loads(path.read_text(encoding="utf-8"))
        require(
            raw["networks"]["Growstar-Test"]["passphrase"]
            == "nur-test-passphrase",
            "Lokale Secret-Datei enthält genau die verifizierte Passphrase",
        )

        store.remove("Growstar-Test")
        require(
            store.get("Growstar-Test") is None,
            "Secret kann für ein WLAN kontrolliert entfernt werden",
        )


def test_privileged_verifier():
    helper = load(
        "install/growstar_network_helper.py",
        "growstar_network_helper_4w6_test",
    )

    ssid = "Growstar-Test"
    password = "korrekte-test-passphrase"

    derived = hashlib.pbkdf2_hmac(
        "sha1",
        password.encode("utf-8"),
        ssid.encode("utf-8"),
        4096,
        dklen=32,
    ).hex()

    helper._wifi_device = lambda: "wlan0"
    helper._device_snapshot = lambda _device: {
        "ssid": ssid,
        "connection": "Growstar-Test",
        "addresses": ["192.0.2.10/24"],
    }
    helper._connection_key_mgmt = lambda _connection: "wpa-psk"
    helper._connection_psk = lambda _connection: derived

    valid = helper._verify_password({
        "ssid": ssid,
        "password": password,
    })

    invalid = helper._verify_password({
        "ssid": ssid,
        "password": "falsche-test-passphrase",
    })

    require(
        valid.get("valid") is True
        and invalid.get("valid") is False,
        "Privilegierter Helper verifiziert Passphrase gegen derived_psk ohne WLAN-Neuverbindung",
    )

    require(
        "password" not in valid
        and "password" not in invalid
        and derived not in json.dumps(valid)
        and derived not in json.dumps(invalid),
        "Verifier gibt weder Passphrase noch gespeicherten derived_psk zurück",
    )


def test_network_service():
    network = load(
        "services/network.py",
        "growstar_network_service_4w6_test",
    )

    class FakeStore:
        def __init__(self):
            self.items = {}
            self.saves = []
            self.removes = []

        def save(self, ssid, secret, *, source):
            self.items[ssid] = secret
            self.saves.append((ssid, secret, source))
            return {"success": True, "stored_for_active": True}

        def get(self, ssid):
            return self.items.get(ssid)

        def remove(self, ssid):
            self.removes.append(ssid)
            return self.items.pop(ssid, None) is not None

        def status(self, ssid=None):
            return {
                "success": True,
                "active_ssid": ssid,
                "stored_for_active": bool(ssid and ssid in self.items),
                "stored_count": len(self.items),
                "source": "test" if ssid in self.items else None,
                "updated_at": None,
                "secret_path": "instance/secrets/network_credentials.json",
            }

    store = FakeStore()
    network.network_secret_store = store
    network.network_permissions = lambda: {
        "write_ready": True,
    }
    network._target_network = lambda ssid: {
        "ssid": ssid,
        "security": "WPA2",
    }

    helper_calls = []

    def helper(payload, timeout=50):
        helper_calls.append(dict(payload))
        return {
            "success": True,
            "already_connected": False,
            "ssid": payload.get("ssid"),
        }

    network._run_network_helper = helper

    result = network.connect_wifi(
        "Growstar-Test",
        "nur-test-passphrase",
    )

    require(
        result.get("success") is True
        and store.saves[-1]
        == (
            "Growstar-Test",
            "nur-test-passphrase",
            "network_connect",
        ),
        "Erfolgreich verifizierter Raspberry-WLAN-Wechsel pflegt zentralen Secret-Store",
    )

    saves_before_failure = len(store.saves)

    def failing_helper(payload, timeout=50):
        return {
            "success": False,
            "error": "simulierter Fehler",
            "rollback_attempted": True,
            "rollback_success": True,
        }

    network._run_network_helper = failing_helper

    try:
        network.connect_wifi(
            "Anderes-Testnetz",
            "nicht-speichern",
        )
    except network.NetworkChangeError:
        pass
    else:
        raise AssertionError("Simulierter WLAN-Fehler wurde nicht propagiert")

    require(
        len(store.saves) == saves_before_failure,
        "Fehlgeschlagener WLAN-Wechsel verändert zentralen Secret-Store nicht",
    )

    network._run_network_helper = lambda payload, timeout=50: {
        "success": True,
        "ssid": payload.get("ssid"),
        "password_updated": True,
    }

    network.update_current_wifi_password(
        "Growstar-Test",
        "neue-test-passphrase",
    )

    require(
        store.saves[-1]
        == (
            "Growstar-Test",
            "neue-test-passphrase",
            "network_password_update",
        ),
        "Erfolgreiche Raspberry-WLAN-Passwortänderung aktualisiert zentralen Secret-Store",
    )

    store.items["Growstar-Test"] = "zentrales-test-secret"
    network._active_wifi_snapshot = lambda device=None: {
        "ssid": "Growstar-Test",
    }
    network._current_wifi_security = lambda _ssid: "WPA2"

    def should_not_read_nm(_ssid):
        raise AssertionError(
            "NetworkManager wurde trotz vorhandenem zentralem Secret gelesen"
        )

    network.get_current_wifi_password = should_not_read_nm

    credentials = network.current_wifi_provisioning_credentials()

    require(
        credentials.get("password") == "zentrales-test-secret"
        and credentials.get("credential_source")
        == "growstar_secret_store",
        "Geräte-Provisionierung bevorzugt passenden zentralen Growstar-Secret-Store",
    )


def test_static_contracts():
    network_source = read("services/network.py")
    secret_source = read("services/network_secrets.py")
    helper_source = read("install/growstar_network_helper.py")
    config_routes = read("routes/config.py")
    hardware_routes = read("routes/hardware.py")
    network_template = read("templates/network.html")
    device_template = read("templates/devices.html")

    require(
        "instance" in secret_source
        and "network_credentials.json" in secret_source
        and "0o600" in secret_source
        and "0o700" in secret_source,
        "Secret-Store liegt lokal unter instance und erzwingt restriktive Dateirechte",
    )

    require(
        '"action": "verify_password"' in network_source
        and 'action == "verify_password"' in helper_source
        and "pbkdf2_hmac" in helper_source
        and "compare_digest" in helper_source,
        "NetworkManager-Helper besitzt eng begrenzte Passphrase-Verifikation für derived_psk",
    )

    require(
        '"/api/config/network/provisioning-secret"' in config_routes
        and '"/system/network/provisioning-secret"' in config_routes
        and "save_current_wifi_provisioning_secret" in config_routes,
        "Netzwerkseite besitzt getrennten Secret-Status- und Schreibendpunkt",
    )

    require(
        'data.get("ssid")' not in config_routes[
            config_routes.index("def system_network_provisioning_secret"):
            config_routes.index("def system_network_connect")
        ],
        "Manuelle Secret-Hinterlegung akzeptiert keine Ziel-SSID aus dem Browser",
    )

    require(
        "Geräte-Provisionierungs-Secret" in network_template
        and "provision-secret-password" in network_template
        and "/system/network/provisioning-secret" in network_template,
        "Netzwerk-UI verwaltet das zentrale Geräte-Provisionierungs-Secret",
    )

    require(
        "provisioning-wifi-password" not in device_template
        and 'data.get("password")' not in hardware_routes
        and "System → Netzwerk öffnen" in device_template,
        "Shelly-UI und Hardware-API besitzen keinen separaten WLAN-Passwortpfad mehr",
    )

    require(
        "current_wifi_provisioning_credentials" in network_source
        and "growstar_secret_store" in network_source,
        "Zentrale Netzwerkquelle wird als bevorzugte Geräte-Provisionierungsquelle exportiert",
    )


def main():
    for rel in (
        "services/network_secrets.py",
        "services/network.py",
        "services/shelly_provisioning.py",
        "install/growstar_network_helper.py",
        "routes/config.py",
        "routes/hardware.py",
        "core/release.py",
        "tests/regression/check_hardware_provisioning_wifi.py",
        "tests/regression/check_network_provisioning_secret.py",
    ):
        ast.parse(read(rel), filename=rel)
        ok("Python-Syntax " + rel)

    test_secret_store()
    test_privileged_verifier()
    test_network_service()
    test_static_contracts()

    release = load(
        "core/release.py",
        "growstar_release_4w6_secret_test",
    )

    require(
        release.GROWSTAR_VERSION == "3.10.6"
        and release.GROWSTAR_INTERNAL_PHASE == "4W.6",
        "Growstar meldet Version 3.10.6 / Phase 4W.6",
    )

    require(
        release.RELEASES[1]["version"] == "3.10.5"
        and release.RELEASES[1]["phase"] == "4W.5",
        "Phase 4W.5 bleibt direkt unter dem neuen Patch dokumentiert",
    )

    print("✅ Phase 4W.6 zentraler WLAN-Secret-Store vollständig")


if __name__ == "__main__":
    main()
