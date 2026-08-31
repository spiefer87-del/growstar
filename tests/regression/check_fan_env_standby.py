#!/usr/bin/env python3
"""Regressionstest für FAN.STANDBY.1."""

from pathlib import Path
from threading import RLock
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import core.control as control
from core.controller_states import resolve_control_state


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def runtime_for(
    *,
    temp=24.0,
    hum=60.0,
    use_temp=False,
    use_hum=True,
    logic="OR",
    standby_enabled=True,
    standby_state=True,
):
    control_states = {
        "env": {
            "power": True,
            "controller": {"level": 80},
        },
    }
    if standby_state:
        control_states["env_standby"] = {
            "power": True,
            "controller": {"level": 25},
        }

    config = {
        "DEVICE_ENV_CONFIG": {
            "fan": {
                "use_temp": use_temp,
                "use_hum": use_hum,
                "logic": logic,
                "direction": "HIGH",
                "standby_enabled": standby_enabled,
            },
        },
        "DEVICE_PARAMS": {
            "fan": {
                "control_states": control_states,
            },
        },
    }

    state = SimpleNamespace(
        live_state={
            "temp": temp,
            "temp_target": 24.0,
            "temp_tol": 1.0,
            "hum": hum,
            "hum_target": 60.0,
            "hum_tol": 5.0,
        }
    )

    return SimpleNamespace(
        tent_id="tent_test",
        config=config,
        state=state,
        state_lock=RLock(),
    )


def main():
    # Rückwärtskompatibilität: Ohne expliziten Zustand darf Standby nie
    # versehentlich den alten Basis-Controller übernehmen.
    require(
        resolve_control_state({}, "env_standby") == {
            "power": False,
            "controller": {},
        },
        "Unkonfiguriertes env_standby bleibt sicher AUS",
    )

    base_only = {"controller": {"level": 99}}
    require(
        resolve_control_state(base_only, "env_standby") == {
            "power": False,
            "controller": {},
        },
        "env_standby besitzt keinen Legacy-Controller-Fallback",
    )

    original_resolve_runtime = control.resolve_runtime
    original_get_device_params = control.get_device_params
    original_apply_device_state = control.apply_device_state

    applied = []

    try:
        control.resolve_runtime = lambda runtime=None: runtime
        control.get_device_params = (
            lambda device, runtime=None:
            runtime.config["DEVICE_PARAMS"][device]
        )
        control.apply_device_state = (
            lambda device, state, runtime=None, reason="":
            applied.append((device, state))
        )

        # Alle überwachten Werte okay -> Standby.
        rt = runtime_for(hum=60.0)
        control.control_fan_env(runtime=rt)
        require(
            applied[-1] == (
                "fan",
                {"power": True, "controller": {"level": 25}},
            ),
            "Normale Umweltwerte schalten auf Standby-Level 25",
        )
        require(
            rt.state.live_state["fan_env_phase"] == "standby",
            "Runtime markiert die Standby-Phase",
        )

        # Feuchte oberhalb Soll + Toleranz -> normale Regelleistung.
        rt = runtime_for(hum=66.0)
        control.control_fan_env(runtime=rt)
        require(
            applied[-1] == (
                "fan",
                {"power": True, "controller": {"level": 80}},
            ),
            "Zu hohe Feuchte schaltet auf ENV-Regelleistung 80",
        )
        require(
            rt.state.live_state["fan_env_phase"] == "regulation",
            "Runtime markiert die Regelphase",
        )

        # Temperatur kann ebenfalls Regelbedarf auslösen.
        rt = runtime_for(
            temp=26.0,
            hum=60.0,
            use_temp=True,
            use_hum=True,
        )
        control.control_fan_env(runtime=rt)
        require(
            applied[-1] == (
                "fan",
                {"power": True, "controller": {"level": 80}},
            ),
            "Zu hohe Temperatur schaltet ebenfalls auf Regelleistung",
        )

        # Standby deaktiviert -> bisheriges AUS-Verhalten.
        rt = runtime_for(
            hum=60.0,
            standby_enabled=False,
        )
        control.control_fan_env(runtime=rt)
        require(
            applied[-1] == (
                "fan",
                {"power": False, "controller": {}},
            ),
            "Deaktiviertes Standby behält historisches ENV-zu-AUS",
        )

        # Fehlender ausgewählter Sensor -> niemals Standby.
        rt = runtime_for(
            hum=None,
            standby_enabled=True,
        )
        control.control_fan_env(runtime=rt)
        require(
            applied[-1] == (
                "fan",
                {"power": False, "controller": {}},
            ),
            "Fehlender ausgewählter Sensor führt sicher zu AUS",
        )
        require(
            rt.state.live_state["fan_env_phase"] == "sensor_unavailable",
            "Fehlende Sensordaten werden explizit markiert",
        )

        # Bei mehreren ausgewählten Sensoren genügt ein fehlender Eingang,
        # um Standby zu blockieren.
        rt = runtime_for(
            temp=None,
            hum=60.0,
            use_temp=True,
            use_hum=True,
        )
        control.control_fan_env(runtime=rt)
        require(
            applied[-1] == (
                "fan",
                {"power": False, "controller": {}},
            ),
            "Ein fehlender von mehreren ausgewählten Sensoren blockiert Standby",
        )

        # Feature aktiv, aber Standby-State fehlt -> sicher AUS.
        rt = runtime_for(
            hum=60.0,
            standby_enabled=True,
            standby_state=False,
        )
        control.control_fan_env(runtime=rt)
        require(
            applied[-1] == (
                "fan",
                {"power": False, "controller": {}},
            ),
            "Aktiviertes Standby ohne gespeicherten Controller-State bleibt AUS",
        )
        require(
            rt.state.live_state["fan_env_phase"] == "standby_unavailable",
            "Unvollständiges Standby wird diagnostisch markiert",
        )

    finally:
        control.resolve_runtime = original_resolve_runtime
        control.get_device_params = original_get_device_params
        control.apply_device_state = original_apply_device_state

    device_page = (
        ROOT / "templates/device_control.html"
    ).read_text(encoding="utf-8")
    dashboard = (
        ROOT / "templates/grow_control.html"
    ).read_text(encoding="utf-8")

    require(
        'id="fan-standby-enabled"' in device_page,
        "Lüfterseite besitzt den Standby-Schalter",
    )
    require(
        'id="fan-standby-controller"' in device_page,
        "Lüfterseite besitzt getrennte Standby-Controllerwerte",
    )
    require(
        '"env_standby"' in device_page,
        "Geräteseite speichert einen separaten env_standby-State",
    )
    require(
        "Standby benötigt einen zugewiesenen Controller" in device_page,
        "UI erklärt die Nichtverfügbarkeit ohne Controller",
    )
    require(
        "Standby · Leistung" in dashboard
        and "Regelung · Leistung" in dashboard,
        "Dashboard unterscheidet Standby und Regelung",
    )

    print("✅ Growstar 3.15.7 / FAN.STANDBY.1 vollständig geprüft")


if __name__ == "__main__":
    main()
