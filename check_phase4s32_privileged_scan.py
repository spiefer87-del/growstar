#!/usr/bin/env python3
"""Phase 4S.3.2 – privilegierter WLAN-Scan."""

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
        "install/growstar_network_helper.py",
        "check_phase4s32_privileged_scan.py",
    ):
        ast.parse(read(rel), filename=rel)
        print("✅ Python-Syntax", rel)

    release = load_module("phase4s32_release", "core/release.py")
    service = load_module("phase4s32_network", "services/network.py")
    helper = load_module("phase4s32_helper", "install/growstar_network_helper.py")

    require(
        release.GROWSTAR_VERSION == "3.7.5"
        and release.GROWSTAR_INTERNAL_PHASE == "4S.3.2",
        "Growstar wurde auf Version 3.7.5 / Phase 4S.3.2 erhöht",
    )

    helper_calls = []
    nmcli_calls = []
    sleep_calls = []

    original_available = service.network_manager_available
    original_helper = service._run_network_helper
    original_read = service._read_wifi_list
    original_run = service._run_nmcli
    original_sleep = service.time.sleep

    try:
        service.network_manager_available = lambda: True

        def fake_helper(payload, timeout=50):
            helper_calls.append((payload, timeout))
            return {
                "success": True,
                "device": "wlan0",
                "scan_requested": True,
            }

        def fake_read(device=None, rescan="auto"):
            nmcli_calls.append(("read", device, rescan))
            return [
                {
                    "ssid": "Home",
                    "signal": 80,
                    "security": "WPA2",
                    "connected": True,
                    "hidden": False,
                },
                {
                    "ssid": "Nachbar",
                    "signal": 55,
                    "security": "WPA2",
                    "connected": False,
                    "hidden": False,
                },
            ]

        def forbidden_direct_nmcli(*args, **kwargs):
            nmcli_calls.append(("direct", args, kwargs))
            raise AssertionError(
                "Force-Scan darf nmcli nicht direkt aus dem Webservice aufrufen"
            )

        service._run_network_helper = fake_helper
        service._read_wifi_list = fake_read
        service._run_nmcli = forbidden_direct_nmcli
        service.time.sleep = lambda seconds: sleep_calls.append(seconds)

        result = service.wifi_scan(force=True)

        require(
            result["success"] is True
            and len(result["networks"]) == 2,
            "Force-Scan liefert nach Helper-Anforderung die WLAN-Liste",
        )
        require(
            helper_calls
            and helper_calls[0][0] == {"action": "scan"},
            "Force-Scan wird ausschließlich über die Helper-Aktion scan angefordert",
        )
        require(
            not any(call[0] == "direct" for call in nmcli_calls),
            "Webservice führt keinen direkten privilegierten nmcli-Scan aus",
        )
        require(
            sleep_calls
            and sleep_calls[0] == service.FORCED_SCAN_SETTLE_SECONDS,
            "Growstar wartet nach der Scan-Anforderung die definierte Settle-Zeit",
        )
        require(
            ("read", "wlan0", "no") in nmcli_calls,
            "Fertige WLAN-Liste wird anschließend mit --rescan no gelesen",
        )

    finally:
        service.network_manager_available = original_available
        service._run_network_helper = original_helper
        service._read_wifi_list = original_read
        service._run_nmcli = original_run
        service.time.sleep = original_sleep

    helper_calls = []
    original_device = helper._wifi_device
    original_run = helper._run_nmcli

    try:
        helper._wifi_device = lambda: "wlan0"

        def fake_helper_nmcli(*args, **kwargs):
            helper_calls.append((args, kwargs))
            return ""

        helper._run_nmcli = fake_helper_nmcli
        scan = helper._scan()

        require(
            scan["success"] is True
            and scan["device"] == "wlan0"
            and scan["scan_requested"] is True,
            "Helper bestätigt die privilegierte Scan-Anforderung",
        )
        require(
            helper_calls
            and helper_calls[0][0] == (
                "device",
                "wifi",
                "rescan",
                "ifname",
                "wlan0",
            ),
            "Helper führt ausschließlich nmcli device wifi rescan auf wlan0 aus",
        )
        require(
            "connect" not in " ".join(helper_calls[0][0])
            and "connection" not in " ".join(helper_calls[0][0]),
            "Helper-Scan verändert keine WLAN-Verbindung oder Profile",
        )

    finally:
        helper._wifi_device = original_device
        helper._run_nmcli = original_run

    helper_text = read("install/growstar_network_helper.py")
    require(
        'if action == "scan":' in helper_text
        and "_json_out(_scan())" in helper_text,
        "Helper-Dispatch enthält die explizite scan-Aktion",
    )
    require(
        "shell=True" not in read("services/network.py")
        and "shell=True" not in helper_text,
        "Service und Helper verwenden weiterhin keine Shell-Ausführung",
    )

    print("✅ Phase 4S.3.2 privilegierter WLAN-Scan vollständig")


if __name__ == "__main__":
    main()
