#!/usr/bin/env python3
"""Regression für harte Tag-/Nacht-Feuchtegrenzen in VPD-AUTO."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
REGRESSION = ROOT / "tests" / "regression"
for path in (ROOT, REGRESSION):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


from check_vpd_intelligent_control import runtime_for, set_inside
from core.vpd_control import _temperature_for_vpd_exact, update_vpd_control


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def night_runtime(*, temp=22.4, hum=70.9):
    runtime = runtime_for(
        mode="AUTO",
        temp=temp,
        hum=hum,
        outside_temp=15.0,
        outside_hum=55.0,
        controller_assigned=True,
    )
    runtime.state.current_profile = "NACHT"
    runtime.state.live_state["profile"] = "NACHT"
    runtime.config.update({
        "MIN_TEMP": 15.0,
        "VPD_TARGET_NIGHT": 0.90,
        "VPD_TOLERANCE_NIGHT": 0.05,
        "VPD_SECONDARY_PRIORITY_NIGHT": "HUMIDITY",
        "VPD_TEMP_MIN_NIGHT": 17.0,
        "VPD_TEMP_MAX_NIGHT": 23.0,
        "VPD_HUM_MIN_NIGHT": 50.0,
        "VPD_HUM_MAX_NIGHT": 62.0,
    })
    fan_states = runtime.config["DEVICE_PARAMS"]["fan"]["control_states"]
    fan_states["env"]["controller"]["level"] = 75
    fan_states["env_standby"]["controller"]["level"] = 75
    return runtime


def main():
    screenshot = night_runtime()
    plan = update_vpd_control(screenshot, now=1000)
    require(
        plan["profile"] == "NACHT"
        and abs(plan["effective_hum_target"] - 56.0) < 0.02
        and abs(plan["setpoints"]["hum"] - 56.0) < 0.02
        and plan["setpoints"]["calculated_hum"] > 62.0
        and plan["setpoints"]["constrained"] is True
        and abs(screenshot.state.live_state["hum_target"] - 56.0) < 0.02
        and abs(screenshot.state.live_state["vpd_hum_target"] - 56.0) < 0.02,
        "Der konkrete Nachtfall strebt statt der Obergrenze den gekoppelten Feuchte-Zielpunkt an",
    )
    require(
        plan["humidity_limit"]["hard"] is True
        and plan["humidity_limit"]["too_high"] is True
        and plan["direction"] == "raise"
        and plan["stage"] == "exhaust"
        and plan["actions"]["humidifier"]["power"] is False,
        "Eine reale Überschreitung bleibt ein aktiver Entfeuchtungsauftrag und kann keine Befeuchtung auslösen",
    )

    target_band = night_runtime()
    target_temperature = _temperature_for_vpd_exact(0.90, 64.0)
    set_inside(target_band, temp=target_temperature, hum=64.0)
    still_wet = update_vpd_control(target_band, now=2000)
    require(
        0.85 <= still_wet["vpd"] <= 0.95
        and still_wet["direction"] == "raise"
        and still_wet["stage"] != "in_band"
        and abs(still_wet["effective_hum_target"] - 56.0) < 0.02,
        "Das Erreichen des VPD-Zielbands beendet die Regelung nicht, solange die harte Feuchte-Obergrenze verletzt ist",
    )

    conflicting = night_runtime(temp=23.0, hum=64.0)
    conflict_plan = update_vpd_control(conflicting, now=3000)
    require(
        conflict_plan["vpd"] > 0.95
        and conflict_plan["direction"] == "raise"
        and conflict_plan["stage"] == "exhaust"
        and conflict_plan["actions"]["heating"]["power"] is False
        and conflict_plan["actions"]["humidifier"]["power"] is False,
        "Bei gleichzeitig zu hoher Feuchte und zu hohem VPD bleiben Heizung und Befeuchter sicher gesperrt",
    )

    transition = night_runtime()
    now = 5000
    heat_plan = None
    for _ in range(5):
        heat_plan = update_vpd_control(transition, now=now)
        now += 60
    require(
        heat_plan["stage"] == "heat"
        and heat_plan["actions"]["heating"]["power"] is True,
        "Bei gleichzeitig zu niedrigem VPD darf nach der Abluft zunächst die begrenzte Temperaturreserve helfen",
    )
    target_temperature = _temperature_for_vpd_exact(0.90, 64.0)
    set_inside(transition, temp=target_temperature, hum=64.0)
    dehumidify = update_vpd_control(transition, now=now - 59)
    require(
        dehumidify["stage"] == "dehumidify"
        and abs(dehumidify["effective_hum_target"] - 56.0) < 0.02
        and dehumidify["actions"]["heating"]["power"] is False
        and dehumidify["actions"]["dehumidifier"]["power"] is True,
        "Am VPD-Ziel endet die Heizhilfe sofort; die verbleibende Feuchteüberschreitung geht an den Entfeuchter",
    )

    too_dry = night_runtime(temp=20.0, hum=49.0)
    dry_plan = update_vpd_control(too_dry, now=4000)
    require(
        50.0 <= dry_plan["effective_hum_target"] <= 62.0
        and dry_plan["humidity_limit"]["too_low"] is True
        and dry_plan["direction"] == "lower"
        and dry_plan["stage"] == "humidify"
        and dry_plan["actions"]["humidifier"]["power"] is True
        and dry_plan["actions"]["dehumidifier"]["power"] is False,
        "Auch die Feuchte-Untergrenze bleibt verbindlich, fordert Befeuchtung an und sperrt gegensinnige Entfeuchtung",
    )

    settings_page = (ROOT / "templates" / "settings.html").read_text(
        encoding="utf-8"
    )
    profile_page = (ROOT / "templates" / "profiles.html").read_text(
        encoding="utf-8"
    )
    log_page = (ROOT / "templates" / "vpd_control_log.html").read_text(
        encoding="utf-8"
    )
    require(
        "verbindlichen Grenzen" in settings_page
        and "verbindlichen Grenzen" in profile_page
        and "VPD-Rechenwert" in log_page
        and "außerhalb der Range" in log_page,
        "Einstellungen, Profile und Regellog erklären die harten Feuchtegrenzen sichtbar",
    )

    print("✅ Harte VPD-Feuchtegrenzen vollständig geprüft")


if __name__ == "__main__":
    main()
