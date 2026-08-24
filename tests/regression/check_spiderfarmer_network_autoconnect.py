#!/usr/bin/env python3
"""Offline regression for Growstar-SF autoconnect after wlan0 reconnect."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def ok(message):
    print("✅", message)


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    ok(message)


def load_network_module():
    path = ROOT / "install/growstar_spiderfarmer_network.py"
    spec = importlib.util.spec_from_file_location(
        "growstar_sf_network_autoconnect_test",
        path,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sample_config():
    return {
        "schema": 1,
        "ssid": "Growstar-SF",
        "password": "UnitTestOnly123456789",
        "wifi_device": "wlan0",
        "uplink_device": "eth0",
        "connection_name": "Growstar-SF",
        "address": "10.42.77.1/24",
        "channel": 6,
        "bridge_port": 18883,
        "upstream_port": 8883,
        "upstream_host": "sf.mqtt.spider-farmer.com",
    }


class Done:
    returncode = 0
    stdout = ""
    stderr = ""


def exercise(existing):
    module = load_network_module()
    calls = []
    secrets = []

    module._connection_exists = lambda name: existing

    def fake_nmcli(*args, **kwargs):
        calls.append(tuple(str(value) for value in args))
        return Done()

    module._nmcli = fake_nmcli
    module._set_profile_secret = (
        lambda name, password: secrets.append((name, password))
    )

    module._ensure_profile(sample_config())
    flattened = "\n".join(" ".join(call) for call in calls)
    return flattened, calls, secrets


def main():
    flattened, calls, secrets = exercise(existing=True)
    require(
        "connection.autoconnect yes" in flattened,
        "Bestehendes Growstar-SF-Profil wird auf autoconnect=yes geheilt",
    )
    require(
        not any("connection add" in " ".join(call) for call in calls),
        "Bestehendes Profil wird nicht unnötig neu angelegt",
    )
    require(
        secrets == [("Growstar-SF", "UnitTestOnly123456789")],
        "Bestehendes Profil behaelt den vorgesehenen Secret-Pfad",
    )

    flattened, calls, secrets = exercise(existing=False)
    require(
        any("connection add" in " ".join(call) for call in calls),
        "Fehlendes Growstar-SF-Profil wird weiterhin angelegt",
    )
    require(
        "connection.autoconnect yes" in flattened,
        "Neu angelegtes Growstar-SF-Profil bekommt autoconnect=yes",
    )
    require(
        "connection.interface-name wlan0" in flattened,
        "Autoconnect bleibt fest an wlan0 gebunden",
    )
    require(
        "ipv4.never-default yes" in flattened,
        "Autoconnect uebernimmt niemals die Ethernet-Default-Route",
    )
    require(
        "802-11-wireless.mode ap" in flattened,
        "Autoconnect aendert den AP-Modus nicht",
    )

    print("✅ SF.1N.1 Autoconnect-Regression vollständig erfolgreich")


if __name__ == "__main__":
    main()
