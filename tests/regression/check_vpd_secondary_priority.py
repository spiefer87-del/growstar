#!/usr/bin/env python3
"""Regression für Growstar 3.16.15 / VPD.CONTROL.9."""

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


def priority_runtime(priority, *, temp=22.0, hum=75.0):
    runtime = runtime_for(
        mode="AUTO",
        temp=temp,
        hum=hum,
        outside_temp=15.0,
        outside_hum=50.0,
        controller_assigned=True,
    )
    runtime.config.update({
        "VPD_TARGET_DAY": 1.10,
        "VPD_TOLERANCE_DAY": 0.05,
        "VPD_SECONDARY_PRIORITY_DAY": priority,
        "VPD_TEMP_MIN_DAY": 20.0,
        "VPD_TEMP_MAX_DAY": 28.0,
        "VPD_HUM_MIN_DAY": 50.0,
        "VPD_HUM_MAX_DAY": 70.0,
        "VPD_EFFECT_WINDOW_MIN": 5,
        "VPD_TEMP_STEP": 0.5,
    })
    fan_states = runtime.config["DEVICE_PARAMS"]["fan"]["control_states"]
    fan_states["env"]["controller"]["level"] = 75
    fan_states["env_standby"]["controller"]["level"] = 75
    return runtime


def advance_to_heat(runtime, start):
    first = update_vpd_control(runtime, now=start)
    heat = first
    now = start
    for _ in range(6):
        if heat["stage"] == "heat":
            break
        now += 60
        heat = update_vpd_control(runtime, now=now)
    return first, heat, now


def main():
    humidity = priority_runtime("HUMIDITY", temp=24.0, hum=63.14)
    humidity_plan = update_vpd_control(humidity, now=1000)
    require(
        humidity_plan["secondary_priority"] == "HUMIDITY"
        and abs(humidity_plan["preferred_hum_target"] - 60.0) < 0.02
        and abs(humidity_plan["preferred_temp_target"] - 22.65) < 0.03
        and humidity_plan["direction"] == "raise",
        "Feuchte-Priorität wählt auf der VPD-Kurve zuerst den Feuchte-Zielwert",
    )

    temperature = priority_runtime("TEMPERATURE", temp=24.0, hum=63.14)
    temperature_plan = update_vpd_control(temperature, now=2000)
    require(
        temperature_plan["secondary_priority"] == "TEMPERATURE"
        and abs(temperature_plan["preferred_temp_target"] - 24.0) < 0.02
        and abs(temperature_plan["preferred_hum_target"] - 63.14) < 0.03
        and temperature_plan["direction"] is None,
        "Temperatur-Priorität wählt auf der VPD-Kurve zuerst den Temperatur-Zielwert",
    )

    at_humidity_target = _temperature_for_vpd_exact(1.10, 60.0)
    set_inside(humidity, temp=at_humidity_target, hum=60.0)
    humidity_target_plan = update_vpd_control(humidity, now=1001)
    require(
        humidity_target_plan["direction"] is None
        and humidity_target_plan["secondary_target_reached"] is True,
        "Im VPD-Band wird bei Feuchte-Priorität keine abweichende Temperatur erzwungen",
    )

    set_inside(temperature, temp=at_humidity_target, hum=60.0)
    temperature_target_plan = update_vpd_control(temperature, now=2001)
    require(
        temperature_target_plan["direction"] == "raise"
        and temperature_target_plan["stage"] == "heat",
        "Im VPD-Band wird bei Temperatur-Priorität der Temperatur-Zielwert nachgeführt",
    )

    flat = priority_runtime("HUMIDITY")
    first, heat, heat_started = advance_to_heat(flat, 3000)
    require(
        first["stage"] == "exhaust" and heat["stage"] == "heat",
        "Feuchte-Priorität prüft nach der geeigneten Abluft zunächst eine Heizstufe",
    )
    set_inside(flat, temp=22.2, hum=75.0)
    early_dehumidifier = update_vpd_control(flat, now=heat_started + 60)
    require(
        early_dehumidifier["stage"] == "dehumidify"
        and early_dehumidifier["actions"]["dehumidifier"]["power"] is True
        and early_dehumidifier["effect"]["humidity_responded"] is False
        and early_dehumidifier["strategy_progress"]["temperature"]["humidity_ineffective"] is True
        and "früh zugeschaltet" in early_dehumidifier["reason"],
        "Sinkt die Feuchte während der Heizprobe nicht, startet der Entfeuchter nach dem ersten Wirkungsfenster",
    )

    falling = priority_runtime("HUMIDITY")
    _, _, falling_heat_started = advance_to_heat(falling, 4000)
    set_inside(falling, temp=22.2, hum=74.5)
    falling_plan = update_vpd_control(falling, now=falling_heat_started + 60)
    require(
        falling_plan["stage"] == "heat"
        and falling_plan["effect"]["humidity_responded"] is True
        and falling_plan["actions"]["dehumidifier"]["power"] is False,
        "Eine messbare Feuchteabnahme lässt die wirksame Heizprobe weiterlaufen",
    )

    temperature_first = priority_runtime("TEMPERATURE")
    first_temperature_plan = update_vpd_control(temperature_first, now=5000)
    require(
        first_temperature_plan["stage"] == "heat"
        and first_temperature_plan["actions"]["heating"]["power"] is True,
        "Temperatur-Priorität nutzt bei zu niedrigem VPD zuerst vorhandene Temperaturreserve",
    )

    settings_page = (ROOT / "templates" / "settings.html").read_text(encoding="utf-8")
    profile_page = (ROOT / "templates" / "profiles.html").read_text(encoding="utf-8")
    log_page = (ROOT / "templates" / "vpd_control_log.html").read_text(encoding="utf-8")
    require(
        "VPD_SECONDARY_PRIORITY_DAY" in settings_page
        and "VPD_SECONDARY_PRIORITY_NIGHT" in profile_page
        and "vpd-log-priority" in log_page
        and "Feuchteabnahme" in log_page,
        "Einstellungen, Profile und Regellog zeigen Priorität und Feuchte-Wirkungsprüfung",
    )

    print("✅ Growstar 3.16.15 / VPD.CONTROL.9 vollständig geprüft")


if __name__ == "__main__":
    main()
