#!/usr/bin/env python3
"""Phase 4S.3.4 – Secret-Reveal und reproduzierbarer Growstar-Systemdienst."""

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
        "check_phase4s34_password_service.py",
    ):
        ast.parse(read(rel), filename=rel)
        print("✅ Python-Syntax", rel)

    release = load_module("phase4s34_release", "core/release.py")
    service = load_module("phase4s34_network", "services/network.py")
    helper = load_module("phase4s34_helper", "install/growstar_network_helper.py")

    require(
        release.GROWSTAR_VERSION == "3.7.7"
        and release.GROWSTAR_INTERNAL_PHASE == "4S.3.4",
        "Growstar wurde auf Version 3.7.7 / Phase 4S.3.4 erhöht",
    )

    routes = read("routes/config.py")
    html = read("templates/network.html")
    helper_text = read("install/growstar_network_helper.py")
    unit = read("install/growstar.service.in")
    installer = read("install/install_growstar_service.sh")

    require(
        '"/system/network/password/show"' in routes
        and '@permission_required("settings.manage")' in routes,
        "Passwortanzeige ist settings.manage-geschützt",
    )
    require(
        'response.headers["Cache-Control"] = "no-store, private, max-age=0"' in routes
        and 'response.headers["Pragma"] = "no-cache"' in routes,
        "Secret-Antwort wird ausdrücklich nicht gecacht",
    )
    require(
        "Passwort anzeigen" in html
        and "data-reveal-index" in html
        and "15000" in html,
        "UI zeigt Secrets nur auf Aktion und maskiert nach 15 Sekunden",
    )

    captured = {}
    old_permissions = service.network_permissions
    old_helper = service._run_network_helper
    try:
        service.network_permissions = lambda: {"write_ready": True, "error": None}

        def fake_helper(payload, timeout=50):
            captured.update(payload)
            return {
                "success": True,
                "ssid": payload["ssid"],
                "password": "Secret123",
            }

        service._run_network_helper = fake_helper
        result = service.get_current_wifi_password("HomeNet")

        require(
            result["success"] is True
            and result["password"] == "Secret123"
            and captured == {"action": "get_password", "ssid": "HomeNet"},
            "Webservice delegiert Secret-Reveal an get_password",
        )
    finally:
        service.network_permissions = old_permissions
        service._run_network_helper = old_helper

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
        helper._connection_psk = lambda connection: "Secret123"

        result = helper._get_password({"ssid": "HomeNet"})
        require(
            result["success"] is True and result["password"] == "Secret123",
            "Helper liefert das PSK der aktuell verbundenen Personal-Verbindung",
        )

        try:
            helper._get_password({"ssid": "FremdesNetz"})
        except helper.HelperError:
            print("✅ Helper blockiert Secret-Reveal für nicht aktive SSIDs")
        else:
            raise AssertionError("Andere SSID wurde nicht blockiert")

        helper._connection_key_mgmt = lambda connection: "wpa-eap"
        try:
            helper._get_password({"ssid": "HomeNet"})
        except helper.HelperError:
            print("✅ Helper blockiert Secret-Reveal für Enterprise-WLAN")
        else:
            raise AssertionError("Enterprise-WLAN wurde nicht blockiert")

    finally:
        for name, value in originals.items():
            setattr(helper, name, value)

    require(
        'if action == "get_password":' in helper_text,
        "Helper-Dispatch enthält die explizite get_password-Aktion",
    )
    require(
        "shell=True" not in helper_text
        and "shell=True" not in read("services/network.py"),
        "Netzwerkpfad verwendet weiterhin keine Shell-Ausführung",
    )

    require(
        "After=network-online.target" in unit
        and "Wants=network-online.target" in unit
        and "Restart=always" in unit
        and "app:flask_app" in unit
        and "gunicorn.conf.py" in unit,
        "growstar.service bildet den bestehenden Gunicorn-Systemdienst ab",
    )
    require(
        "User=__GROWSTAR_USER__" in unit
        and "Group=__GROWSTAR_GROUP__" in unit
        and "WorkingDirectory=__GROWSTAR_DIR__" in unit,
        "Service-Vorlage verwendet dynamische Installationswerte",
    )
    require(
        "/home/pi5/growstar" not in installer
        and 'SERVICE_USER="pi5"' not in installer,
        "Service-Installer enthält keinen fest codierten Raspberry-Benutzer oder Projektpfad",
    )
    require(
        '"${SERVICE_USER}" == "root"' in installer
        and "Growstar darf nicht als root laufen" in installer,
        "Service-Installer verweigert root als Growstar-Dienstbenutzer",
    )
    require(
        "systemctl enable" in installer
        and "--start" in installer
        and "systemctl restart" in installer
        and "START_NOW" in installer,
        "Installer unterstützt sicheren Install-only-Modus und explizites Starten",
    )
    require(
        "Bestehende Drop-ins" in installer
        and "rm -rf" not in installer,
        "Bestehende systemd-Drop-ins werden nicht gelöscht",
    )
    require(
        "GROWSTAR_HTTPS_ONLY" not in unit,
        "Basis-Service erzwingt kein HTTPS und bleibt Setup-Hotspot-kompatibel",
    )

    print("✅ Phase 4S.3.4 Secret-Reveal und Systemdienst vollständig")


if __name__ == "__main__":
    main()
