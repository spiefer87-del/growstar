#!/usr/bin/env python3
"""Phase 4S.3.5 – Passphrase vs. abgeleiteter 64-Hex-PSK."""

from pathlib import Path
import ast
import importlib.util

ROOT = Path(__file__).resolve().parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def load_module(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    for rel in (
        "core/release.py",
        "services/network.py",
        "routes/config.py",
        "install/growstar_network_helper.py",
        "check_phase4s35_wifi_credential_type.py",
    ):
        ast.parse(read(rel), filename=rel)
        print("✅ Python-Syntax", rel)

    release = load_module("phase4s35_release", "core/release.py")
    service = load_module("phase4s35_network", "services/network.py")
    helper = load_module(
        "phase4s35_helper",
        "install/growstar_network_helper.py",
    )

    require(
        release.GROWSTAR_VERSION == "3.7.8"
        and release.GROWSTAR_INTERNAL_PHASE == "4S.3.5",
        "Growstar wurde auf Version 3.7.8 / Phase 4S.3.5 erhöht",
    )

    require(
        helper._credential_type("a" * 64) == "derived_psk",
        "64-stelliger Hex-Wert wird als derived_psk erkannt",
    )
    require(
        helper._credential_type("MeinWLANPasswort123") == "passphrase",
        "Normale WLAN-Passphrase wird als passphrase erkannt",
    )
    require(
        helper._credential_type("g" * 64) == "passphrase",
        "64 Zeichen ohne reines Hex werden nicht fälschlich als derived_psk erkannt",
    )

    originals = {
        "_wifi_device": helper._wifi_device,
        "_device_snapshot": helper._device_snapshot,
        "_connection_key_mgmt": helper._connection_key_mgmt,
        "_connection_psk": helper._connection_psk,
    }

    try:
        helper._wifi_device = lambda: "wlan0"
        helper._device_snapshot = lambda device: {
            "device": device,
            "connection": "HomeProfile",
            "ssid": "HomeNet",
            "addresses": ["192.168.1.20/24"],
            "gateway": "192.168.1.1",
        }
        helper._connection_key_mgmt = lambda connection: "wpa-psk"

        helper._connection_psk = lambda connection: "A1" * 32
        derived = helper._get_password({"ssid": "HomeNet"})

        require(
            derived["success"] is True
            and derived["credential_type"] == "derived_psk"
            and derived["revealable"] is False,
            "Helper meldet abgeleiteten PSK als nicht rücklesbare Passphrase",
        )
        require(
            "password" not in derived,
            "Abgeleiteter 64-Hex-PSK wird nicht in der Helper-Antwort übertragen",
        )

        helper._connection_psk = lambda connection: "MeinEchtesPasswort123"
        phrase = helper._get_password({"ssid": "HomeNet"})

        require(
            phrase["success"] is True
            and phrase["credential_type"] == "passphrase"
            and phrase["revealable"] is True
            and phrase["password"] == "MeinEchtesPasswort123",
            "Echte gespeicherte Passphrase bleibt gezielt rücklesbar",
        )

    finally:
        for name, value in originals.items():
            setattr(helper, name, value)

    old_permissions = service.network_permissions
    old_helper = service._run_network_helper

    try:
        service.network_permissions = lambda: {
            "write_ready": True,
            "error": None,
        }
        service._run_network_helper = lambda payload, timeout=15: {
            "success": True,
            "ssid": "HomeNet",
            "credential_type": "derived_psk",
            "revealable": False,
            "credential_length": 64,
        }

        result = service.get_current_wifi_password("HomeNet")

        require(
            result["success"] is True
            and result["credential_type"] == "derived_psk"
            and result["revealable"] is False
            and "password" not in result,
            "Webservice gibt derived_psk-Metadaten ohne Secret weiter",
        )

    finally:
        service.network_permissions = old_permissions
        service._run_network_helper = old_helper

    html = read("templates/network.html")
    require(
        "Originalpasswort nicht auslesbar" in html
        and 'data.credential_type === "derived_psk"' in html,
        "Netzwerkseite kennzeichnet derived_psk verständlich",
    )
    require(
        "15000" in html,
        "Rücklesbare Passphrasen werden weiterhin nach 15 Sekunden maskiert",
    )

    helper_text = read("install/growstar_network_helper.py")
    require(
        '("Return" if False else "")' not in helper_text,
        "Keine Test-Platzhalter im Helper vorhanden",
    )
    require(
        "shell=True" not in helper_text
        and "shell=True" not in read("services/network.py"),
        "Netzwerkpfad verwendet weiterhin keine Shell-Ausführung",
    )

    print("✅ Phase 4S.3.5 WLAN-Credential-Typ vollständig")


if __name__ == "__main__":
    main()
