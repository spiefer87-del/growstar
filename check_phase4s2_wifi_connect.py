#!/usr/bin/env python3
"""Phase 4S.2 – sicherer WLAN-Wechsel und Erstinbetriebnahme-Grundlage."""

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
        "gunicorn.conf.py",
        "check_phase4s2_wifi_connect.py",
    ):
        ast.parse(read(rel), filename=rel)
        print("✅ Python-Syntax", rel)

    release = load_module("phase4s2_release", "core/release.py")

    require(
        release.GROWSTAR_VERSION == "3.7.2"
        and release.GROWSTAR_INTERNAL_PHASE == "4S.2",
        "Growstar wurde auf Version 3.7.2 / Phase 4S.2 erhöht",
    )

    routes = read("routes/config.py")
    html = read("templates/network.html")
    gunicorn = read("gunicorn.conf.py")
    service = load_module("phase4s2_network", "services/network.py")

    require(
        '"/api/config/network/capabilities"' in routes
        and '"/system/network/connect"' in routes,
        "Capabilities-API und schreibende WLAN-Aktion sind registriert",
    )

    require(
        '@permission_required("settings.manage")' in routes,
        "WLAN-Wechsel verlangt settings.manage",
    )

    require(
        '"0.0.0.0:8001"' in gunicorn
        and '"192.168.178.66:8001"' not in gunicorn,
        "Gunicorn ist nicht mehr an die alte feste LAN-IP gebunden",
    )

    require(
        "/api/config/network/capabilities" in html
        and "/system/network/connect" in html
        and "WLAN-Verwaltung bereit" in html,
        "Netzwerkseite besitzt Berechtigungsanzeige und WLAN-Verbindungsdialog",
    )

    require(
        "shell=True" not in read("services/network.py"),
        "NetworkManager-Aufrufe verwenden weiterhin keine Shell",
    )

    # --------------------------------------------------------
    # Polkit-Berechtigungen
    # --------------------------------------------------------
    original_available = service.network_manager_available
    original_run = service._run_nmcli

    try:
        service.network_manager_available = lambda: True
        service._run_nmcli = lambda *args, **kwargs: (
            "org.freedesktop.NetworkManager.network-control:yes\n"
            "org.freedesktop.NetworkManager.settings.modify.system:yes\n"
            "org.freedesktop.NetworkManager.wifi.share.protected:yes\n"
        )

        permissions = service.network_permissions()

        require(
            permissions["write_ready"] is True
            and permissions["hotspot_ready"] is True,
            "NetworkManager-Schreib- und Hotspot-Rechte werden korrekt erkannt",
        )
    finally:
        service.network_manager_available = original_available
        service._run_nmcli = original_run

    # --------------------------------------------------------
    # Passwort darf nicht in argv landen
    # --------------------------------------------------------
    calls = []
    secret = "SuperSecret123"

    original_permissions = service.network_permissions
    original_target = service._target_network
    original_wifi_device = service._wifi_device
    original_active = service._active_wifi_snapshot
    original_wait = service._wait_for_target_wifi
    original_rollback = service._rollback_wifi
    original_run = service._run_nmcli

    try:
        service.network_permissions = lambda: {
            "write_ready": True,
            "hotspot_ready": True,
            "error": None,
        }
        service._target_network = lambda ssid: {
            "ssid": ssid,
            "security": "WPA2",
            "hidden": False,
        }
        service._wifi_device = lambda: "wlan0"
        service._active_wifi_snapshot = lambda device=None: {
            "device": "wlan0",
            "connection": "Old WiFi",
            "ssid": "OldNet",
            "addresses": ["192.168.1.10/24"],
            "gateway": "192.168.1.1",
        }
        service._wait_for_target_wifi = lambda ssid, device, timeout=12: {
            "device": "wlan0",
            "connection": "New WiFi",
            "ssid": ssid,
            "addresses": ["192.168.50.20/24"],
            "gateway": "192.168.50.1",
        }
        service._rollback_wifi = lambda previous, device: {
            "attempted": True,
            "success": True,
            "error": None,
        }

        def fake_run(*args, **kwargs):
            calls.append((args, kwargs))
            return ""

        service._run_nmcli = fake_run

        result = service.connect_wifi("TestNet", secret)

        require(
            result["success"] is True
            and result["ssid"] == "TestNet",
            "Simulierter WPA2-WLAN-Wechsel wird erfolgreich bestätigt",
        )

        argv_text = "\n".join(
            " ".join(map(str, args))
            for args, _kwargs in calls
        )

        require(
            secret not in argv_text,
            "WLAN-Passwort erscheint nicht in nmcli-Prozessargumenten",
        )

        require(
            any(
                kwargs.get("input_text") == secret + "\n"
                for _args, kwargs in calls
            ),
            "WLAN-Passwort wird ausschließlich über stdin an nmcli übergeben",
        )

    finally:
        service.network_permissions = original_permissions
        service._target_network = original_target
        service._wifi_device = original_wifi_device
        service._active_wifi_snapshot = original_active
        service._wait_for_target_wifi = original_wait
        service._rollback_wifi = original_rollback
        service._run_nmcli = original_run

    # --------------------------------------------------------
    # Verifikationsfehler muss Rollback auslösen
    # --------------------------------------------------------
    rollback_calls = []

    original_permissions = service.network_permissions
    original_target = service._target_network
    original_wifi_device = service._wifi_device
    original_active = service._active_wifi_snapshot
    original_wait = service._wait_for_target_wifi
    original_rollback = service._rollback_wifi
    original_run = service._run_nmcli

    try:
        service.network_permissions = lambda: {
            "write_ready": True,
            "hotspot_ready": True,
            "error": None,
        }
        service._target_network = lambda ssid: {
            "ssid": ssid,
            "security": "WPA2",
            "hidden": False,
        }
        service._wifi_device = lambda: "wlan0"
        service._active_wifi_snapshot = lambda device=None: {
            "device": "wlan0",
            "connection": "Old WiFi",
            "ssid": "OldNet",
            "addresses": ["192.168.1.10/24"],
            "gateway": "192.168.1.1",
        }
        service._wait_for_target_wifi = lambda ssid, device, timeout=12: None
        service._run_nmcli = lambda *args, **kwargs: ""

        def fake_rollback(previous, device):
            rollback_calls.append((previous, device))
            return {
                "attempted": True,
                "success": True,
                "error": None,
            }

        service._rollback_wifi = fake_rollback

        try:
            service.connect_wifi("BrokenNet", secret)
        except service.NetworkChangeError as exc:
            require(
                exc.rollback_attempted is True
                and exc.rollback_success is True,
                "Fehlende IPv4-Verifikation meldet erfolgreichen Rollback",
            )
        else:
            raise AssertionError("NetworkChangeError wurde erwartet")

        require(
            rollback_calls
            and rollback_calls[0][0]["connection"] == "Old WiFi",
            "Vorherige aktive Verbindung wird als Rollback-Ziel verwendet",
        )

    finally:
        service.network_permissions = original_permissions
        service._target_network = original_target
        service._wifi_device = original_wifi_device
        service._active_wifi_snapshot = original_active
        service._wait_for_target_wifi = original_wait
        service._rollback_wifi = original_rollback
        service._run_nmcli = original_run

    require(
        any(
            "Setup-Hotspot" in item or "Erstinbetriebnahme" in item
            for item in release.RELEASES[0]["changes"]
        ),
        "Patch Note dokumentiert die Vorbereitung der codefreien Erstinbetriebnahme",
    )

    print("✅ Phase 4S.2 WLAN-Wechsel vollständig")


if __name__ == "__main__":
    main()
