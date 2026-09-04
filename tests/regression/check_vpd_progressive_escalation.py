#!/usr/bin/env python3
"""Regression für Growstar 3.16.8 / VPD.CONTROL.3."""

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


def _same_fan_levels(runtime, *, first_now=1000):
    first = update_vpd_control(runtime, now=first_now)
    plans = [first]
    now = first_now
    while plans[-1]["stage"] == "exhaust" and plans[-1]["fan_level"] < 100:
        now += 301
        plans.append(update_vpd_control(runtime, now=now))
    return plans, now


def main():
    progressive = runtime_for(mode="MONITOR", controller_assigned=True)
    fan_states = progressive.config["DEVICE_PARAMS"]["fan"]["control_states"]
    fan_states["env"]["controller"]["level"] = 75
    fan_states["env_standby"]["controller"]["level"] = 75

    fan_plans, now = _same_fan_levels(progressive)
    require(
        [plan["fan_level"] for plan in fan_plans]
        == [75, 85, 95, 100]
        and all(plan["stage"] == "exhaust" for plan in fan_plans),
        "Die Abluft steigt trotz unverändert schwacher VPD-Messung in konfigurierten Prozentpunkten von 75 bis 100",
    )
    require(
        fan_plans[-1]["strategy_progress"]["fan"] == {
            "level": 100,
            "minimum": 75,
            "maximum": 100,
            "complete": False,
        }
        and "Temperaturziel" in fan_plans[-1]["next_step_label"],
        "Das Dashboard veröffentlicht den echten Abluft-Fortschritt und den bevorstehenden Temperaturweg",
    )

    now += 301
    heat_start = update_vpd_control(progressive, now=now)
    require(
        heat_start["stage"] == "heat"
        and heat_start["effective_temp_target"] == 24.5
        and heat_start["strategy_progress"]["fan"]["complete"] is True,
        "Die Temperatur wird erst nach einem vollständigen Prüfintervall auf maximaler Abluft angehoben",
    )

    targets = []
    for measured in (24.5, 25.0, 25.5):
        now += 301
        set_inside(progressive, temp=measured, hum=75.0)
        plan = update_vpd_control(progressive, now=now)
        targets.append(plan["effective_temp_target"])
    require(
        targets == [25.0, 25.5, 26.0]
        and plan["stage"] == "heat",
        "Jede erreichte Temperaturstufe gibt den nächsten sicheren Schritt bis 26 Grad frei",
    )

    now += 301
    set_inside(progressive, temp=26.0, hum=75.0)
    final = update_vpd_control(progressive, now=now)
    require(
        final["stage"] == "dehumidify"
        and final["strategy_progress"]["temperature"]["complete"] is True
        and final["effective_temp_target"] == 26.0,
        "Erst die vollständig erreichte Temperatur-Obergrenze gibt den Entfeuchter frei",
    )

    stalled = runtime_for(mode="MONITOR")
    stalled_states = stalled.config["DEVICE_PARAMS"]["fan"]["control_states"]
    stalled_states["env"]["controller"]["level"] = 80
    stalled_states["env_standby"]["controller"]["level"] = 80
    update_vpd_control(stalled, now=1000)
    stalled_heat = update_vpd_control(stalled, now=1301)
    stalled_wait = update_vpd_control(stalled, now=1602)
    stalled_fallback = update_vpd_control(stalled, now=1903)
    require(
        stalled_heat["stage"] == "heat"
        and stalled_wait["stage"] == "heat"
        and stalled_wait["strategy_progress"]["temperature"]["stall_windows"] == 1
        and stalled_fallback["stage"] == "dehumidify",
        "Eine träge Heizung erhält ein zweites Prüfintervall; erst echte Reaktionslosigkeit beendet den Temperaturweg",
    )

    no_dehumidifier = runtime_for(
        mode="MONITOR",
        device_modes={
            "fan": "ENV",
            "heating": "ENV",
            "humidifier": "ENV",
            "dehumidifier": "OFF",
        },
    )
    no_dehum_states = no_dehumidifier.config["DEVICE_PARAMS"]["fan"]["control_states"]
    no_dehum_states["env"]["controller"]["level"] = 80
    no_dehum_states["env_standby"]["controller"]["level"] = 80
    update_vpd_control(no_dehumidifier, now=1000)
    update_vpd_control(no_dehumidifier, now=1301)
    update_vpd_control(no_dehumidifier, now=1602)
    limited = update_vpd_control(no_dehumidifier, now=1903)
    rechecked = update_vpd_control(no_dehumidifier, now=2204)
    require(
        limited["stage"] == "limited"
        and limited["effect"]["next_evaluation_sec"] == 300
        and rechecked["stage"] == "limited"
        and "ausgeschöpft" in rechecked["reason"],
        "Ohne letzte ENV-Stufe bleibt LIMITED sicher, aber wird regelmäßig neu bewertet statt einzufrieren",
    )

    vpd_log = (ROOT / "templates" / "vpd_control_log.html").read_text(
        encoding="utf-8"
    )
    settings = (ROOT / "templates" / "settings.html").read_text(
        encoding="utf-8"
    )
    require(
        'id="vpd-log-progress"' in vpd_log
        and "strategy_progress" in vpd_log
        and "schwächere Einzelmessung beendet den Stufenweg nicht" in settings,
        "Regellog und Einstellungsseite erklären den vollständigen Stufenweg nachvollziehbar",
    )

    print("✅ Growstar 3.16.8 / VPD.CONTROL.3 vollständig geprüft")


if __name__ == "__main__":
    main()
