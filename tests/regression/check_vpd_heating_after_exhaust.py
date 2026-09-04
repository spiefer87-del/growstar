#!/usr/bin/env python3
"""Regression für Growstar 3.16.11 / VPD.CONTROL.5."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
REGRESSION = ROOT / "tests" / "regression"
for path in (ROOT, REGRESSION):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


from check_vpd_intelligent_control import runtime_for, set_inside
from core.vpd_control import update_vpd_control


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def screenshot_runtime():
    runtime = runtime_for(
        mode="AUTO",
        temp=23.9,
        hum=69.9,
        outside_temp=15.0,
        outside_hum=55.0,
        controller_assigned=True,
        device_modes={
            "fan": "ENV",
            "heating": "ENV",
            "humidifier": "OFF",
            "dehumidifier": "OFF",
        },
    )
    runtime.config.update({
        "VPD_TARGET_DAY": 1.10,
        "VPD_TOLERANCE_DAY": 0.05,
        "VPD_TEMP_MIN_DAY": 20.0,
        "VPD_TEMP_MAX_DAY": 26.0,
        "VPD_HUM_MIN_DAY": 50.0,
        "VPD_HUM_MAX_DAY": 60.0,
        "VPD_EFFECT_WINDOW_MIN": 5,
        "VPD_TEMP_STEP": 0.5,
        "VPD_FAN_STEP": 10,
    })
    fan_states = runtime.config["DEVICE_PARAMS"]["fan"]["control_states"]
    fan_states["env"]["controller"]["level"] = 75
    fan_states["env_standby"]["controller"]["level"] = 75
    # Eine absichtlich extreme klassische Toleranz darf den eigenen
    # VPD-Temperaturschritt nicht blockieren.
    runtime.state.live_state["temp_tol"] = 5.0
    return runtime


def exhaust_to_heat(runtime):
    plans = []
    now = 1000
    for _ in range(4):
        plans.append(update_vpd_control(runtime, now=now))
        now += 301
    heat = update_vpd_control(runtime, now=now)
    return plans, heat, now


def main():
    runtime = screenshot_runtime()
    fan_plans, heat, now = exhaust_to_heat(runtime)

    require(
        [plan["fan_level"] for plan in fan_plans] == [75, 85, 95, 100]
        and all(plan["stage"] == "exhaust" for plan in fan_plans),
        "Der reale Fehlerfall prüft die Abluft weiterhin vollständig von 75 bis 100 Prozent",
    )
    require(
        heat["stage"] == "heat"
        and heat["effective_temp_target"] == 24.4
        and heat["actions"]["heating"]["power"] is True
        and heat["actions"]["fan"]["controller"]["level"] == 100,
        "Nach erfolgloser Maximalabluft beginnt die Heizung trotz Feuchte-Arbeitsfenster und klassischer Toleranz",
    )
    require(
        abs(fan_plans[0]["effective_hum_target"] - 62.91) < 0.02
        and abs(heat["effective_hum_target"] - 64.01) < 0.02,
        "Der mathematische Feuchtesollwert folgt jeder freigegebenen Temperaturstufe live",
    )

    targets = []
    heating_commands = []
    for measured_temp in (24.4, 24.9, 25.4, 25.9):
        now += 301
        set_inside(runtime, temp=measured_temp, hum=69.9)
        plan = update_vpd_control(runtime, now=now)
        targets.append(plan["effective_temp_target"])
        heating_commands.append(plan["actions"]["heating"]["power"])

    require(
        targets == [24.9, 25.4, 25.9, 26.0]
        and plan["stage"] == "heat"
        and all(heating_commands[:3]),
        "Der Heizweg läuft in geprüften 0,5-Grad-Schritten bis zur erlaubten Obergrenze von 26 Grad",
    )

    now += 301
    set_inside(runtime, temp=26.0, hum=69.9)
    exhausted = update_vpd_control(runtime, now=now)
    require(
        exhausted["stage"] == "limited"
        and exhausted["effective_temp_target"] == 26.0
        and exhausted["strategy_progress"]["temperature"]["complete"] is True
        and exhausted["actions"]["fan"]["controller"]["level"] == 100
        and abs(exhausted["effective_hum_target"] - 67.28) < 0.02,
        "Erst die reale Temperatur-Obergrenze beendet den Heizweg; Abluft 100 und der passende Feuchterechenwert bleiben sichtbar",
    )

    recovered = screenshot_runtime()
    _, recovered_heat, recovered_now = exhaust_to_heat(recovered)
    require(
        recovered_heat["stage"] == "heat",
        "Der zweite Prüflauf erreicht die aktive Heizstufe",
    )
    set_inside(recovered, temp=25.0, hum=65.0)
    in_band = update_vpd_control(recovered, now=recovered_now + 10)
    require(
        in_band["stage"] == "in_band"
        and in_band["direction"] is None
        and in_band["effective_temp_target"] == 25.0
        and in_band["actions"]["heating"]["power"] is False,
        "Sobald der gemessene VPD das Zielband erreicht, stoppt Growstar die Heizung sofort statt bis 26 Grad zu überschwingen",
    )

    settings_page = (ROOT / "templates" / "settings.html").read_text(
        encoding="utf-8"
    )
    profile_page = (ROOT / "templates" / "profiles.html").read_text(
        encoding="utf-8"
    )
    require(
        "Feuchte min/max" in settings_page
        and "verkürzt keine noch erlaubte Temperaturreserve" in profile_page,
        "Einstellungs- und Profilseite erklären Temperaturgrenze und Feuchte-Arbeitsfenster eindeutig",
    )

    print("✅ Growstar 3.16.11 / VPD.CONTROL.5 vollständig geprüft")


if __name__ == "__main__":
    main()
