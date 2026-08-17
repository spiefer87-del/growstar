#!/usr/bin/env python3
"""Phase 4S.3 – frischer WLAN-Scan und gezielte NetworkManager-Freigabe."""

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
        "check_phase4s3_network_permissions.py",
    ):
        ast.parse(read(rel), filename=rel)
        print("✅ Python-Syntax", rel)

    release = load_module("phase4s3_release", "core/release.py")
    service = load_module("phase4s3_network", "services/network.py")

    require(
        release.GROWSTAR_VERSION == "3.7.3"
        and release.GROWSTAR_INTERNAL_PHASE == "4S.3",
        "Growstar wurde auf Version 3.7.3 / Phase 4S.3 erhöht",
    )

    routes = read("routes/config.py")
    html = read("templates/network.html")
    rule = read("install/49-growstar-network.rules.in")
    installer = read("install/install_network_permissions.sh")

    require(
        'wifi_scan(force=force)' in routes
        and 'request.args.get("refresh")' in routes,
        "WLAN-API unterstützt einen expliziten Force-Scan",
    )

    require(
        '/api/config/network/wifi?refresh=1' in html
        and 'refresh(true)' in html,
        "Netzwerkseite erzwingt beim Laden/Aktualisieren einen frischen Scan",
    )

    calls = []
    original_available = service.network_manager_available
    original_run = service._run_nmcli
    try:
        service.network_manager_available = lambda: True

        def fake_run(*args, **kwargs):
            calls.append((args, kwargs))
            return "*:TestNet:80:WPA2\n"

        service._run_nmcli = fake_run
        result = service.wifi_scan(force=True)
        require(result["success"] is True and result["rescan"] == "yes", "Force-Scan wird als frisch markiert")
        require(
            any("--rescan" in args and "yes" in args for args, _ in calls),
            "Force-Scan ruft nmcli mit --rescan yes auf",
        )
    finally:
        service.network_manager_available = original_available
        service._run_nmcli = original_run

    original_available = service.network_manager_available
    original_run = service._run_nmcli
    try:
        service.network_manager_available = lambda: True
        service._run_nmcli = lambda *args, **kwargs: (
            "org.freedesktop.NetworkManager.network-control:yes\n"
            "org.freedesktop.NetworkManager.settings.modify.own:yes\n"
            "org.freedesktop.NetworkManager.settings.modify.system:auth\n"
            "org.freedesktop.NetworkManager.wifi.share.protected:yes\n"
        )
        permissions = service.network_permissions()
        require(
            permissions["write_ready"] is True
            and permissions["profile_scope"] == "private",
            "modify-own reicht für private Growstar-WLAN-Profile aus",
        )
        require(
            permissions["hotspot_ready"] is True,
            "Geschützte Hotspot-Berechtigung wird separat erkannt",
        )
    finally:
        service.network_manager_available = original_available
        service._run_nmcli = original_run

    calls = []
    secret = "TestPasswort123"
    originals = {
        "network_permissions": service.network_permissions,
        "_target_network": service._target_network,
        "_wifi_device": service._wifi_device,
        "_active_wifi_snapshot": service._active_wifi_snapshot,
        "_wait_for_target_wifi": service._wait_for_target_wifi,
        "_rollback_wifi": service._rollback_wifi,
        "_run_nmcli": service._run_nmcli,
    }
    try:
        service.network_permissions = lambda: {
            "write_ready": True,
            "profile_scope": "private",
            "hotspot_ready": True,
            "error": None,
        }
        service._target_network = lambda ssid: {"ssid": ssid, "security": "WPA2", "hidden": False}
        service._wifi_device = lambda: "wlan0"
        service._active_wifi_snapshot = lambda device=None: {
            "device": "wlan0", "connection": "Alt", "ssid": "AltNet",
            "addresses": ["192.168.1.20/24"], "gateway": "192.168.1.1",
        }
        service._wait_for_target_wifi = lambda ssid, device, timeout=12: {
            "device": "wlan0", "connection": "Neu", "ssid": ssid,
            "addresses": ["192.168.50.20/24"], "gateway": "192.168.50.1",
        }
        service._rollback_wifi = lambda previous, device: {"attempted": True, "success": True, "error": None}

        def fake_run(*args, **kwargs):
            calls.append((args, kwargs))
            return ""

        service._run_nmcli = fake_run
        result = service.connect_wifi("NeuesNetz", secret)
        require(result["success"] is True, "Simulierter privater WLAN-Wechsel ist erfolgreich")
        require(
            any("private" in args and "yes" in args for args, _ in calls),
            "Neue WLAN-Verbindung fordert nmcli private yes an",
        )
        argv = "\n".join(" ".join(map(str, args)) for args, _ in calls)
        require(secret not in argv, "WLAN-Passwort bleibt weiterhin aus den Prozessargumenten")
    finally:
        for name, value in originals.items():
            setattr(service, name, value)

    require(
        'subject.system_unit == "growstar.service"' in rule
        and 'subject.user == "__GROWSTAR_SERVICE_USER__"' in rule,
        "Polkit-Regel ist an Growstar-Systemdienst und Dienstbenutzer gebunden",
    )
    require(
        "settings.modify.own" in rule
        and "settings.modify.system" not in rule,
        "Polkit-Regel gewährt modify-own, aber kein modify-system",
    )
    require(
        "systemctl show" in installer
        and "User --value" in installer
        and "pi5" not in installer,
        "Installer ermittelt den Dienstbenutzer dynamisch statt ihn fest zu codieren",
    )
    require(
        "shell=True" not in read("services/network.py"),
        "NetworkManager-Aufrufe verwenden weiterhin keine Shell-Ausführung",
    )

    print("✅ Phase 4S.3 NetworkManager-Freigabe vollständig")


if __name__ == "__main__":
    main()
