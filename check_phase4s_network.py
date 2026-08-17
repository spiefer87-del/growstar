#!/usr/bin/env python3
"""Phase 4S – Network Management read-only Regressionstest."""

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


def load_network():
    spec = importlib.util.spec_from_file_location(
        "phase4s_network",
        ROOT / "services" / "network.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_release():
    spec = importlib.util.spec_from_file_location(
        "phase4s_release",
        ROOT / "core" / "release.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    for rel in (
        "services/network.py",
        "routes/config.py",
        "check_phase4s_network.py",
        "core/release.py",
    ):
        ast.parse(read(rel), filename=rel)
        print("✅ Python-Syntax", rel)

    release = load_release()
    require(
        release.GROWSTAR_VERSION == "3.7.0"
        and release.GROWSTAR_INTERNAL_PHASE == "4S",
        "Growstar wurde auf Version 3.7.0 / Phase 4S erhöht",
    )

    routes = read("routes/config.py")
    require(
        '"/system/network"' in routes
        and '"/api/config/network/status"' in routes
        and '"/api/config/network/wifi"' in routes,
        "Netzwerkseite und beide read-only APIs sind registriert",
    )
    require(
        '@permission_required("settings.view")' in routes,
        "Netzwerkzugriffe sind zusätzlich mit settings.view geschützt",
    )

    system_html = read("templates/system.html")
    network_html = read("templates/network.html")
    require(
        'href="/system/network"' in system_html,
        "System-Dashboard verlinkt das Netzwerkmanagement",
    )
    require(
        "/api/config/network/status" in network_html
        and "/api/config/network/wifi" in network_html,
        "Netzwerkseite lädt Status und WLAN-Scan",
    )

    service = load_network()
    require(
        service._split_escaped(r"wifi:Home\:Lab:connected")
        == ["wifi", "Home:Lab", "connected"],
        "Escaped nmcli-Doppelpunkte werden korrekt geparst",
    )

    original_which = service.shutil.which
    try:
        service.shutil.which = lambda name: None
        status = service.network_status()
        scan = service.wifi_scan()
        require(
            status["success"] is False
            and status["manager_available"] is False
            and scan["success"] is False,
            "Fehlendes nmcli degradiert diagnostisch statt mit Exception",
        )
    finally:
        service.shutil.which = original_which

    original_available = service.network_manager_available
    original_run = service._run_nmcli
    try:
        service.network_manager_available = lambda: True
        service._run_nmcli = lambda *args: (
            r"*:Growstar\:Lab:88:WPA2" "\n"
            r":Nachbar:41:WPA2" "\n"
            r":Nachbar:72:WPA2" "\n"
        )
        scan = service.wifi_scan()
        require(
            scan["success"] is True
            and scan["networks"][0]["ssid"] == "Growstar:Lab"
            and scan["networks"][0]["connected"] is True,
            "Aktives WLAN und escaped SSID werden korrekt erkannt",
        )
        require(
            len([n for n in scan["networks"] if n["ssid"] == "Nachbar"]) == 1
            and next(n for n in scan["networks"] if n["ssid"] == "Nachbar")["signal"] == 72,
            "Doppelte SSIDs werden auf den stärksten Access Point reduziert",
        )
    finally:
        service.network_manager_available = original_available
        service._run_nmcli = original_run

    require(
        "shell=True" not in read("services/network.py"),
        "NetworkManager-Aufrufe verwenden keine Shell-Ausführung",
    )

    print("✅ Phase 4S Network Management vollständig")


if __name__ == "__main__":
    main()
