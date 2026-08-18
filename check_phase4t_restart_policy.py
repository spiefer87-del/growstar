#!/usr/bin/env python3
"""Phase 4T – konfigurierbares Neustart-Verhalten pro Aktor."""

from pathlib import Path
import ast
import importlib.util
import sys
import threading
import types
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent

TEST_DEVICE_NAMES = (
    "heating", "fan", "light", "vent", "irrigation",
    "humidifier", "dehumidifier", "light2", "vent2",
    "aux1", "aux2", "aux3", "aux4",
)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def load_module(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakeRuntime:
    def __init__(self):
        self.tent_id = "tent_test"
        self.name = "Testzelt"
        self.config = {
            "IP_LIGHT": "192.0.2.10",
            "RELAY_LIGHT": 0,
            "IP_HEATING": "192.0.2.11",
            "RELAY_HEATING": 0,
            "DEVICE_LABELS": {},
        }
        self.state_lock = threading.RLock()
        self.state = SimpleNamespace(
            light_on=False,
            heating_on=False,
            live_state={
                "light": False,
                "heating": False,
            },
        )
        self.persisted = 0

    def persist_config(self):
        self.persisted += 1
        return True


def install_import_stubs():
    core_pkg = types.ModuleType("core")
    core_pkg.__path__ = [str(ROOT / "core")]
    sys.modules.setdefault("core", core_pkg)

    devices = types.ModuleType("core.devices")
    devices.DEVICE_NAMES = TEST_DEVICE_NAMES
    devices.get_device_icon = lambda device: "•"
    devices.get_device_label = lambda device, runtime=None: device
    devices.validate_device_name = lambda device: (
        device if device in TEST_DEVICE_NAMES
        else (_ for _ in ()).throw(ValueError(f"Unbekanntes Gerät: {device}"))
    )
    sys.modules["core.devices"] = devices

    runtime_mod = types.ModuleType("core.runtime")
    runtime_mod.resolve_runtime = lambda runtime=None: runtime
    sys.modules["core.runtime"] = runtime_mod

    actuators = types.ModuleType("core.actuators")
    actuators.get_shelly_relay_state = lambda *args, **kwargs: False
    actuators.switch_shelly = lambda *args, **kwargs: True
    sys.modules["core.actuators"] = actuators

    assignments = types.ModuleType("core.hardware_assignments")
    assignments.DEVICE_HARDWARE = {}
    assignments.device_display_label = lambda cfg, device: device
    sys.modules["core.hardware_assignments"] = assignments


def main():
    for rel in (
        "app.py",
        "core/release.py",
        "core/restart_policy.py",
        "services/restart_policy.py",
        "routes/restart_policy.py",
        "tools/prepare_phase4t_restart.py",
        "check_phase4t_restart_policy.py",
    ):
        ast.parse(read(rel), filename=rel)
        print("✅ Python-Syntax", rel)

    release = load_module("phase4t_release", "core/release.py")

    install_import_stubs()
    policy = load_module("core.restart_policy", "core/restart_policy.py")
    service = load_module("phase4t_service", "services/restart_policy.py")

    require(
        release.GROWSTAR_VERSION == "3.7.9"
        and release.GROWSTAR_INTERNAL_PHASE == "4T",
        "Growstar wurde auf Version 3.7.9 / Phase 4T erhöht",
    )

    require(
        policy.DEFAULT_RESTART_POLICY["light"] == "KEEP"
        and policy.DEFAULT_RESTART_POLICY["light2"] == "KEEP"
        and policy.DEFAULT_RESTART_POLICY["heating"] == "OFF",
        "Sichere Default-Policy: Licht KEEP, Heizung OFF",
    )

    rt = FakeRuntime()
    snapshot = policy.get_restart_policy(rt)
    require(
        snapshot["light"] == "KEEP"
        and snapshot["heating"] == "OFF",
        "Fehlende Config wird read-only mit den Defaults ergänzt",
    )

    result = policy.update_restart_policy(
        {"light": "OFF", "heating": "KEEP"},
        runtime=rt,
    )
    require(
        result["policy"]["light"] == "OFF"
        and result["policy"]["heating"] == "KEEP"
        and rt.persisted == 1,
        "Stationsbezogene Policy wird persistiert",
    )

    try:
        policy.update_restart_policy({"unknown": "KEEP"}, runtime=rt)
    except ValueError:
        pass
    else:
        raise AssertionError("Unbekannter Aktor wurde nicht blockiert")
    print("✅ Unbekannte Aktoren werden blockiert")

    try:
        policy.update_restart_policy({"light": "ON"}, runtime=rt)
    except ValueError:
        pass
    else:
        raise AssertionError("Unsichere ON-Aktion wurde nicht blockiert")
    print("✅ Unsichere Restart-Aktion ON wird blockiert")

    # Service: KEEP darf keinerlei physischen Write auslösen.
    rt = FakeRuntime()
    rt.config["RESTART_POLICY"] = {
        "light": "KEEP",
        "heating": "OFF",
    }

    writes = []
    reads = []

    service.DEVICE_HARDWARE = {
        "light": {
            "ip_key": "IP_LIGHT",
            "relay_key": "RELAY_LIGHT",
        },
        "heating": {
            "ip_key": "IP_HEATING",
            "relay_key": "RELAY_HEATING",
        },
    }
    service.device_display_label = lambda cfg, device: device
    service.get_restart_action = (
        lambda device, runtime=None:
        runtime.config["RESTART_POLICY"].get(device, "OFF")
    )
    service.switch_shelly = (
        lambda host, relay, enabled, timeout=2:
        writes.append((host, relay, enabled)) or True
    )
    service.get_shelly_relay_state = (
        lambda host, relay, timeout=2:
        reads.append((host, relay)) or False
    )

    result = service.apply_shutdown_restart_policy(rt)

    require(
        not any(host == "192.0.2.10" for host, _, _ in writes),
        "KEEP erzeugt keinen Shelly-Schreibzugriff",
    )
    require(
        ("192.0.2.11", 0, False) in writes,
        "OFF sendet einen echten AUS-Befehl trotz Runtime-State=False",
    )
    require(
        ("192.0.2.11", 0) in reads
        and result["devices"]["heating"]["verified"] is True,
        "OFF wird direkt am Relay verifiziert",
    )

    app = read("app.py")
    require(
        "apply_shutdown_restart_policy" in app
        and "set_device(device, False" not in app,
        "app.shutdown_backend verwendet die Restart-Policy statt pauschalem Alles-AUS",
    )
    require(
        "for device, meta in DEVICE_HARDWARE.items()" in app
        and 'f"{device}_on"' in app,
        "Start-Synchronisierung ist generisch und umfasst AUX-Aktoren",
    )

    route = read("routes/restart_policy.py")
    template = read("templates/restart_policy.html")
    require(
        '"/grow-control/setup/restart-policy"' in route
        and '"/api/tents/<tent_id>/restart-policy"' in route,
        "Setup-Seite und stationsbezogene Restart-Policy-API sind registriert",
    )
    require(
        "Zustand beibehalten" in template
        and "Sicher AUS" in template
        and "Stromausfall" in template,
        "UI erklärt KEEP/OFF und die Stromausfall-Grenze",
    )

    activate = read("install/activate_phase4t_without_old_shutdown.sh")
    require(
        "SIGSTOP" in activate
        and "prepare_phase4t_restart.py" in activate
        and "SIGKILL" in activate,
        "Einmalige Aktivierung umgeht den alten Alles-AUS-Shutdown kontrolliert",
    )
    stop_cmd = 'systemctl kill --kill-whom=all --signal=SIGSTOP "${SERVICE}"'
    prepare_cmd = 'sudo -u "${SERVICE_USER}" python3 "${PREPARE}"'
    kill_cmd = 'systemctl kill --kill-whom=all --signal=SIGKILL "${SERVICE}"'
    require(
        stop_cmd in activate
        and prepare_cmd in activate
        and kill_cmd in activate
        and activate.index(stop_cmd)
            < activate.index(prepare_cmd)
            < activate.index(kill_cmd),
        "Aktivierungsreihenfolge ist Freeze -> Policy -> alter Worker beenden",
    )

    print("✅ Phase 4T Restart-Policy vollständig")


if __name__ == "__main__":
    main()
