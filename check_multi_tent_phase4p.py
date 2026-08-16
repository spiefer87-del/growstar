#!/usr/bin/env python3
"""Phase 4P – frei benennbare Universal-Aktoren aux1..aux4.

Statische Architektur-/Regressionstests. Keine Netzwerk- oder Shelly-Zugriffe.
"""

from pathlib import Path
import ast
import importlib.util
import sys
import threading
import types

ROOT = Path(__file__).resolve().parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    for rel in (
        "core/devices.py",
        "core/actuators.py",
        "core/config.py",
        "core/config_update.py",
        "core/state.py",
        "core/hardware_assignments.py",
        "core/live_preflight.py",
        "core/watchdog_health.py",
        "routes/dashboard.py",
    ):
        ast.parse(read(rel), filename=rel)
        print("✅ Python-Syntax", rel)

    devices = read("core/devices.py")
    actuators = read("core/actuators.py")
    config = read("core/config.py")
    config_update = read("core/config_update.py")
    state = read("core/state.py")
    hardware = read("core/hardware_assignments.py")
    preflight = read("core/live_preflight.py")
    watchdog = read("core/watchdog_health.py")
    dashboard = read("routes/dashboard.py")
    hub = read("templates/grow_control_dashboard.html")
    design = read("templates/design.html")
    grow = read("templates/grow_control.html")
    energy = read("templates/energie.html")
    control = read("core/control.py")
    main_thread = read("threads/main.py")
    safety_core = read("core/safety.py")
    shelly_service = read("services/shelly.py")
    live_service = read("services/live_control.py")
    energy_service = read("services/energy.py")

    require(
        'AUX_DEVICE_NAMES = ("aux1", "aux2", "aux3", "aux4")' in devices,
        "Vier stabile Universal-Slots sind zentral definiert",
    )

    for device in ("aux1", "aux2", "aux3", "aux4"):
        suffix = device.upper()
        require(f'"{device}":' in hardware, f"{device} besitzt Hardware-Metadaten")
        require(f'"IP_{suffix}"' in hardware, f"{device} besitzt eigenen IP-Key")
        require(f'"RELAY_{suffix}"' in hardware, f"{device} besitzt eigenen Relay-Key")
        require(f"device='{device}'" in grow, f"{device} besitzt eine individuelle Dashboard-Kachel")

    require(
        '"aux1": {"label": "Wasserpumpen"' in devices,
        "aux1 startet sichtbar als Wasserpumpen",
    )
    require(
        '"aux1": "OFF"' in config
        and '"aux2": "OFF"' in config
        and '"aux3": "OFF"' in config
        and '"aux4": "OFF"' in config,
        "Alle Universal-Slots starten sicher im Modus OFF",
    )
    require(
        '"DEVICE_LABELS": {' in config
        and '"aux1": "Wasserpumpen"' in config,
        "Stationsbezogene Anzeigenamen besitzen sichere Defaults",
    )
    require(
        "aux1_on=False" in state
        and "aux2_on=False" in state
        and "aux3_on=False" in state
        and "aux4_on=False" in state,
        "Alle Universal-Aktoren besitzen explizite sichere Runtime-Startzustände",
    )
    require(
        "DEVICE_LABEL_MAX_LENGTH = 48" in devices
        and "normalize_device_label" in devices,
        "Freie Namen werden zentral normalisiert und begrenzt",
    )
    require(
        "if not is_aux_device(device):" in devices,
        "Bestehende feste Aktoren bleiben absichtlich nicht frei benennbar",
    )
    require(
        "AUX_DEVICE_NAMES, normalize_device_label" in config_update
        and 'if key == "DEVICE_LABELS":' in config_update
        and "set(value) - set(AUX_DEVICE_NAMES)" in config_update,
        "Config-API akzeptiert freie Namen nur für aux1..aux4",
    )

    require(
        all(
            f'if mode == "{mode}"' in control
            for mode in ("OFF", "ON", "TIME", "INTERVAL", "ENV")
        )
        and "evaluate_env_conditions(device" in control,
        "Bestehende generische Regelung liefert OFF/ON/TIME/INTERVAL/ENV auch für aux-Slots",
    )
    require(
        "for device in DEVICE_NAMES:" in main_thread,
        "Hauptregelkreis übernimmt aux1..aux4 automatisch über DEVICE_NAMES",
    )
    require(
        "for device in DEVICE_NAMES:" in safety_core,
        "Safety-Matrix übernimmt aux1..aux4 automatisch über DEVICE_NAMES",
    )
    require(
        "for device, meta in DEVICE_HARDWARE.items()" in shelly_service,
        "Shelly-Failsafe übernimmt aux1..aux4 automatisch über DEVICE_HARDWARE",
    )
    require(
        live_service.count("for device, meta in DEVICE_HARDWARE.items()") >= 2,
        "LIVE-Seeding und LIVE→SHADOW Safe-Off erfassen Universal-Aktoren generisch",
    )
    require(
        "for device, meta in DEVICE_HARDWARE.items()" in energy_service,
        "Bestehender Energiepoll erfasst zugeordnete Universal-Aktoren automatisch",
    )

    require(
        "def set_auxiliary(" in actuators
        and "_set_shelly_device(" in actuators
        and "if device in _AUX_DEVICE_NAMES:" in actuators,
        "Universal-Aktoren benutzen denselben zentralen Aktorpfad",
    )
    require(
        'state_attr=f"{device}_on"' in actuators
        and "live_key=device" in actuators,
        "Jeder Universal-Aktor besitzt getrennten Runtime-/Live-State",
    )
    require(
        'if not rt.control_enabled or getattr(rt, "disarming", False):' in actuators,
        "SHADOW-/DISARMING-Hard-Block bleibt vor realer Hardware",
    )
    require(
        'override.get("force_off")' in actuators
        and 'override.get("block_on")' in actuators,
        "Phase-4I Safety-Overrides bleiben im physischen Aktorpfad",
    )

    require(
        "DeviceHardwareRequiredError" in devices
        and "_assert_hardware_for_active_mode" in devices,
        "Phase-4L Hardware-Guard bleibt unverändert wirksam",
    )
    require(
        "_endpoint_owners" in hardware
        and "_assert_assignment_change_safe" in hardware,
        "Doppelbelegungs- und LIVE-Reassignment-Guards bleiben erhalten",
    )
    require(
        "def device_display_label(cfg, device):" in hardware
        and '"label": device_display_label(cfg, device)' in hardware,
        "Verbindungen/Hardware verwenden den stationsbezogenen Anzeigenamen",
    )
    require(
        "device_display_label(cfg, device)" in preflight,
        "LIVE-Preflight verwendet den freien Anzeigenamen",
    )
    require(
        "device_display_label(cfg, device)" in watchdog,
        "Watchdog verwendet den freien Anzeigenamen",
    )
    require(
        "get_device_label(device, runtime=runtime)" in dashboard,
        "Gerätesteuerseite erhält den stationsbezogenen Anzeigenamen",
    )

    require(
        'text: "ARMING"' in hub
        and "tent.arming || tent.live_requested" in hub,
        "Grow-Control-Hub zeigt den bestehenden ARMING-Zustand wieder explizit",
    )

    require(
        "Freie Zusatzgeräte" in design
        and "DEVICE_LABELS: readAuxLabels()" in design
        and 'maxlength="48"' in design,
        "Design-Seite kann vier Zusatzgeräte frei benennen",
    )
    require(
        "defaultVisible:false" in design
        and "return !AUX_DEVICES.includes(key);" in grow,
        "Neue Universal-Kacheln sind auf bestehenden Dashboards standardmäßig verborgen",
    )
    require(
        all(f'id="{device}-card"' in grow for device in ("aux1", "aux2", "aux3", "aux4")),
        "Vier individuelle Dashboard-Kacheln sind vorhanden",
    )
    require(
        '"aux1", "aux2", "aux3", "aux4"' in grow
        and "updateDevice(name, state)" in grow,
        "Dashboard aktualisiert Runtime-/Hardware-State auch für aux1..aux4",
    )

    require(
        "displayDeviceLabel" in energy
        and "refreshStationDeviceLabels" in energy
        and "DEVICE_LABEL_CACHE_MS = 30000" in energy,
        "Energieansicht löst freie Gerätenamen stationsbezogen und gecacht auf",
    )
    require(
        "/api/tents/${encodeURIComponent(tentId)}/config" in energy
        and "fetch('/api/energy/overview'" in energy,
        "Energie nutzt nur bestehende APIs; kein neuer Shelly-/Messpfad",
    )
    require(
        "/api/energy/history?range=" not in energy,
        "Energieübersicht bleibt weiterhin von der History-/Diagramm-API getrennt",
    )

    print("✅ Phase 4P Universal-Aktoren vollständig")


def dynamic_aux_actuator_check():
    """Prüft den neuen aux-Pfad isoliert ohne echte Requests."""

    old_modules = dict(sys.modules)
    try:
        for key in list(sys.modules):
            if key == "core" or key.startswith("core.") or key == "requests":
                sys.modules.pop(key, None)

        core = types.ModuleType("core")
        core.__path__ = []
        sys.modules["core"] = core

        runtime_module = types.ModuleType("core.runtime")
        runtime_module.resolve_runtime = lambda runtime=None: runtime
        sys.modules["core.runtime"] = runtime_module

        requests = types.ModuleType("requests")
        requests.post = lambda *a, **k: None
        requests.get = lambda *a, **k: None
        sys.modules["requests"] = requests

        spec = importlib.util.spec_from_file_location(
            "phase4p_actuators",
            ROOT / "core" / "actuators.py",
        )
        actuator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(actuator)

        state = types.SimpleNamespace(
            aux1_on=False,
            live_state={"aux1": False},
        )
        runtime = types.SimpleNamespace(
            tent_id="tent_aux",
            state=state,
            config={
                "IP_AUX1": "192.0.2.40",
                "RELAY_AUX1": 0,
                "DEVICE_LABELS": {"aux1": "Wasserpumpen"},
            },
            state_lock=threading.RLock(),
            control_enabled=False,
            disarming=False,
            shadow_outputs={},
            safety_overrides={},
            safety_lock=threading.RLock(),
        )

        calls = []
        actuator.switch_shelly = (
            lambda ip, relay, enabled, timeout=3:
            calls.append((ip, int(relay), bool(enabled))) or True
        )

        actuator.set_device("aux1", True, runtime=runtime)
        require(
            not calls and runtime.shadow_outputs.get("aux1") is True,
            "aux1 bleibt in SHADOW physisch hart gesperrt",
        )

        runtime.control_enabled = True
        actuator.set_device("aux1", True, runtime=runtime)
        require(
            calls[-1] == ("192.0.2.40", 0, True)
            and state.aux1_on is True
            and state.live_state["aux1"] is True,
            "aux1 nutzt LIVE denselben bestätigten Shelly-State-Pfad",
        )

        runtime.safety_overrides = {
            "aux1": {
                "force_off": True,
                "block_on": True,
                "can_attempt_off": True,
                "reason": "Test-Failsafe",
            }
        }
        actuator.set_device("aux1", True, runtime=runtime)
        require(
            calls[-1] == ("192.0.2.40", 0, False)
            and state.aux1_on is False,
            "aux1 wird durch bestehenden Safety-Override sicher AUS erzwungen",
        )

    finally:
        sys.modules.clear()
        sys.modules.update(old_modules)


if __name__ == "__main__":
    main()
    dynamic_aux_actuator_check()
