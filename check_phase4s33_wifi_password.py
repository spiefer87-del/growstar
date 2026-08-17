#!/usr/bin/env python3
"""Phase 4S.3.3 – Passwort der bestehenden WLAN-Verbindung."""

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
        "check_phase4s33_wifi_password.py",
    ):
        ast.parse(read(rel), filename=rel)
        print("✅ Python-Syntax", rel)

    release = load_module("phase4s33_release", "core/release.py")
    service = load_module("phase4s33_network", "services/network.py")
    helper = load_module("phase4s33_helper", "install/growstar_network_helper.py")

    require(
        release.GROWSTAR_VERSION == "3.7.6"
        and release.GROWSTAR_INTERNAL_PHASE == "4S.3.3",
        "Growstar wurde auf Version 3.7.6 / Phase 4S.3.3 erhöht",
    )

    routes = read("routes/config.py")
    html = read("templates/network.html")
    helper_text = read("install/growstar_network_helper.py")

    require(
        '"/system/network/password"' in routes
        and '@permission_required("settings.manage")' in routes,
        "Passwort-API ist registriert und verlangt settings.manage",
    )
    require(
        "Passwort ändern" in html
        and 'data-password-index=' in html
        and "wifi-password-confirm" in html,
        "Netzwerkseite bietet Passwort ändern mit Bestätigung an",
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
                "password_updated": True,
            }

        service._run_network_helper = fake_helper
        result = service.update_current_wifi_password(
            "TestNet",
            "NeuesPasswort123",
        )

        require(
            result["success"] is True
            and captured["action"] == "update_password",
            "Webservice delegiert die Passwortänderung an update_password",
        )
    finally:
        service.network_permissions = old_permissions
        service._run_network_helper = old_helper

    editor_calls = []
    nmcli_calls = []
    originals = {
        "_wifi_device": helper._wifi_device,
        "_device_snapshot": helper._device_snapshot,
        "_connection_key_mgmt": helper._connection_key_mgmt,
        "_connection_psk": helper._connection_psk,
        "_run_nmcli_editor": helper._run_nmcli_editor,
        "_run_nmcli": helper._run_nmcli,
        "_wait_for_target": helper._wait_for_target,
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
        helper._connection_psk = lambda connection: "AltesPasswort123"
        helper._run_nmcli_editor = lambda connection, password: editor_calls.append(
            (connection, password)
        )

        def fake_nmcli(*args, **kwargs):
            nmcli_calls.append((args, kwargs))
            return ""

        helper._run_nmcli = fake_nmcli
        helper._wait_for_target = lambda ssid, device: {
            "device": device,
            "connection": "HomeProfile",
            "ssid": ssid,
            "addresses": ["192.168.1.21/24"],
            "gateway": "192.168.1.1",
        }

        result = helper._update_password({
            "ssid": "HomeNet",
            "password": "NeuesPasswort123",
        })

        require(
            result["success"] is True
            and editor_calls == [("HomeProfile", "NeuesPasswort123")],
            "Neues PSK wird über den interaktiven Editor gespeichert",
        )

        argv = "\n".join(" ".join(map(str, args)) for args, _ in nmcli_calls)
        require(
            "NeuesPasswort123" not in argv
            and "AltesPasswort123" not in argv,
            "Altes und neues Passwort erscheinen nicht in nmcli-Prozessargumenten",
        )
    finally:
        for name, value in originals.items():
            setattr(helper, name, value)

    editor_calls = []
    originals = {
        "_wifi_device": helper._wifi_device,
        "_device_snapshot": helper._device_snapshot,
        "_connection_key_mgmt": helper._connection_key_mgmt,
        "_connection_psk": helper._connection_psk,
        "_run_nmcli_editor": helper._run_nmcli_editor,
        "_run_nmcli": helper._run_nmcli,
        "_wait_for_target": helper._wait_for_target,
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
        helper._connection_psk = lambda connection: "AltesPasswort123"
        helper._run_nmcli_editor = lambda connection, password: editor_calls.append(
            (connection, password)
        )

        activation_count = {"value": 0}

        def fake_nmcli(*args, **kwargs):
            if "connection" in args and "up" in args:
                activation_count["value"] += 1
                if activation_count["value"] == 1:
                    raise helper.HelperError("neues Passwort abgelehnt")
            return ""

        helper._run_nmcli = fake_nmcli
        helper._wait_for_target = lambda ssid, device: {
            "device": device,
            "connection": "HomeProfile",
            "ssid": ssid,
            "addresses": ["192.168.1.20/24"],
            "gateway": "192.168.1.1",
        }

        result = helper._update_password({
            "ssid": "HomeNet",
            "password": "FalschesNeuesPasswort",
        })

        require(
            result["success"] is False
            and result["rollback_attempted"] is True
            and result["rollback_success"] is True,
            "Fehlerhafte Passwortänderung führt zum erfolgreichen Rollback",
        )
        require(
            editor_calls == [
                ("HomeProfile", "FalschesNeuesPasswort"),
                ("HomeProfile", "AltesPasswort123"),
            ],
            "Rollback schreibt das bisherige PSK zurück",
        )
    finally:
        for name, value in originals.items():
            setattr(helper, name, value)

    require(
        'if action == "update_password":' in helper_text,
        "Helper-Dispatch enthält update_password",
    )
    require(
        "shlex.quote(password)" in helper_text
        and "input=editor_input" in helper_text,
        "PSK wird gequotet und nur per stdin an den nmcli-Editor übergeben",
    )
    require(
        "shell=True" not in helper_text
        and "shell=True" not in read("services/network.py"),
        "Helper und Service verwenden weiterhin keine Shell-Ausführung",
    )

    print("✅ Phase 4S.3.3 WLAN-Passwortänderung vollständig")


if __name__ == "__main__":
    main()
