#!/usr/bin/env python3
"""Phase 4S.3.1 – stabiler Scan und privilegierter Netzwerk-Helper."""

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
        "check_phase4s31_network_helper.py",
    ):
        ast.parse(read(rel), filename=rel)
        print("✅ Python-Syntax", rel)

    release = load_module("phase4s31_release", "core/release.py")
    service = load_module("phase4s31_network", "services/network.py")

    require(
        release.GROWSTAR_VERSION == "3.7.4"
        and release.GROWSTAR_INTERNAL_PHASE == "4S.3.1",
        "Growstar wurde auf Version 3.7.4 / Phase 4S.3.1 erhöht",
    )

    html = read("templates/network.html")
    installer = read("install/install_network_permissions.sh")
    helper = read("install/growstar_network_helper.py")
    deprecated_rule = read("install/49-growstar-network.rules.in")

    require(
        "device" in read("services/network.py")
        and '"wifi",' in read("services/network.py")
        and '"rescan",' in read("services/network.py")
        and "FORCED_SCAN_SETTLE_SECONDS" in read("services/network.py")
        and 'rescan="no"' in read("services/network.py"),
        "Force-Scan fordert separat einen Scan an und liest erst danach mit --rescan no",
    )

    calls = []
    original_available = service.network_manager_available
    original_device = service._wifi_device
    original_run = service._run_nmcli
    original_sleep = service.time.sleep

    try:
        service.network_manager_available = lambda: True
        service._wifi_device = lambda: "wlan0"
        service.time.sleep = lambda seconds: calls.append(("sleep", seconds))

        def fake_run(*args, **kwargs):
            calls.append((args, kwargs))
            if "list" in args:
                return (
                    "*:Home:80:WPA2\n"
                    ":Nachbar:55:WPA2\n"
                )
            return ""

        service._run_nmcli = fake_run
        scan = service.wifi_scan(force=True)

        require(
            scan["success"] is True and len(scan["networks"]) == 2,
            "Erzwungener Scan liefert die erst nach Wartephase gelesene WLAN-Liste",
        )
        require(
            any(item[0] == "sleep" and item[1] >= 4 for item in calls if isinstance(item, tuple)),
            "Force-Scan enthält eine definierte Settle-Wartephase",
        )
        argv_calls = [item[0] for item in calls if isinstance(item, tuple) and item and isinstance(item[0], tuple)]
        require(
            any("rescan" in args and "ifname" in args for args in argv_calls),
            "NetworkManager-Scan wird explizit angefordert",
        )
        require(
            any("--rescan" in args and "no" in args and "list" in args for args in argv_calls),
            "Fertige Access-Point-Liste wird ohne zweiten Scan gelesen",
        )
    finally:
        service.network_manager_available = original_available
        service._wifi_device = original_device
        service._run_nmcli = original_run
        service.time.sleep = original_sleep

    original_available = service.network_manager_available
    original_helper = service._run_network_helper
    try:
        service.network_manager_available = lambda: True
        service._run_network_helper = lambda payload, timeout=50: {
            "success": True,
            "write_ready": True,
            "hotspot_ready": True,
            "backend": "privileged-helper",
            "profile_scope": "system",
        }

        caps = service.network_permissions()

        require(
            caps["write_ready"] is True
            and caps["profile_scope"] == "system"
            and caps["backend"] == "privileged-helper",
            "Capabilities verwenden den privilegierten Helper statt Polkit-Subject-Matching",
        )
    finally:
        service.network_manager_available = original_available
        service._run_network_helper = original_helper

    captured = {}
    originals = {
        "network_permissions": service.network_permissions,
        "_target_network": service._target_network,
        "_run_network_helper": service._run_network_helper,
    }

    try:
        service.network_permissions = lambda: {
            "write_ready": True,
            "profile_scope": "system",
            "error": None,
        }
        service._target_network = lambda ssid: {
            "ssid": ssid,
            "security": "WPA2",
            "hidden": False,
        }

        def fake_helper(payload, timeout=50):
            captured.update(payload)
            return {
                "success": True,
                "ssid": payload["ssid"],
                "profile_scope": "system",
                "rollback_attempted": False,
                "rollback_success": False,
            }

        service._run_network_helper = fake_helper

        result = service.connect_wifi("TestNet", "SuperSecret123")
        require(result["success"] is True, "WLAN-Wechsel wird an den Helper delegiert")
        require(
            captured["action"] == "connect"
            and captured["ssid"] == "TestNet"
            and captured["password"] == "SuperSecret123",
            "Helper erhält die validierte WLAN-Anfrage über stdin-JSON",
        )
    finally:
        for name, value in originals.items():
            setattr(service, name, value)

    require(
        "shell=True" not in read("services/network.py")
        and "shell=True" not in helper,
        "Weder Webdienst noch Netzwerk-Helper verwenden Shell-Ausführung",
    )
    require(
        '"/usr/local/libexec/growstar-network-helper"' in installer
        and '"/etc/sudoers.d/growstar-network"' in installer
        and "visudo -cf" in installer,
        "Installer richtet root-eigenen Helper und validierte sudoers-Regel ein",
    )
    require(
        "rm -f \"${OLD_POLKIT_RULE}\"" in installer,
        "Installer entfernt die alte Phase-4S.3-Polkit-Regel",
    )
    require(
        "growstar.service" in helper
        and "/proc/self/cgroup" in helper,
        "Helper verweigert Aufrufe außerhalb des Growstar-Systemdienstes",
    )
    require(
        '"private",' in helper and '"no",' in helper,
        "Neue WLAN-Profile werden systemweit für Boot-Autoconnect angelegt",
    )
    require(
        'input_text = password + "\\n"' in helper
        and "password" not in helper.split("args.extend([", 1)[1].split("])", 1)[0],
        "WLAN-Passwort wird im Helper nicht als nmcli-Argument verwendet",
    )
    require(
        "Scan läuft" in html
        and "Privilegierter Growstar-Netzwerk-Helper aktiv" in html,
        "Netzwerkseite zeigt Scanfortschritt und Helper-Status verständlich an",
    )
    require(
        "NICHT mehr installiert" in deprecated_rule,
        "Alte Polkit-Vorlage ist eindeutig als veraltet markiert",
    )

    print("✅ Phase 4S.3.1 stabiler Scan und Netzwerk-Helper vollständig")


if __name__ == "__main__":
    main()
