#!/usr/bin/env python3
"""Regression für Growstar 3.16.12 / VPD.CONTROL.6."""

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


def main():
    fast = runtime_for(mode="MONITOR")
    first = update_vpd_control(fast, now=1000)
    before = update_vpd_control(fast, now=1059)
    stepped = update_vpd_control(fast, now=1060)
    require(
        first["effect"]["cadence"]["phase"] == "fast"
        and first["effect"]["window_sec"] == 60
        and first["effect"]["max_window_sec"] == 300
        and first["effect"]["next_evaluation_sec"] == 60
        and before["fan_level"] == 25
        and before["effect"]["next_evaluation_sec"] == 1
        and stepped["fan_level"] == 35,
        "Neue Regelstufen werden exakt eine Minute beobachtet, bevor höchstens ein Aktorschritt folgt",
    )

    stable = runtime_for(mode="MONITOR", temp=24.0, hum=63.0)
    stable_first = update_vpd_control(stable, now=2000)
    stable_fast = update_vpd_control(stable, now=2059)
    settling = update_vpd_control(stable, now=2060)
    stable_long = update_vpd_control(stable, now=2600)
    require(
        stable_first["stage"] == "in_band"
        and stable_first["effect"]["cadence"]["phase"] == "fast"
        and stable_fast["effect"]["window_sec"] == 60
        and settling["effect"]["cadence"]["phase"] == "settling"
        and settling["effect"]["window_sec"] == 120
        and stable_long["effect"]["cadence"]["phase"] == "stable"
        and stable_long["effect"]["window_sec"] == 300,
        "Ein ruhiges Zielband wechselt nach einer Minute in die Beruhigungsphase und nach zehn Minuten in den Fünf-Minuten-Stabilbetrieb",
    )

    set_inside(stable, temp=24.0, hum=75.0)
    drift = update_vpd_control(stable, now=2601)
    require(
        drift["direction"] == "raise"
        and drift["effect"]["cadence"]["phase"] == "fast"
        and drift["effect"]["window_sec"] == 60
        and drift["effect"]["next_evaluation_sec"] == 60,
        "Jede neue Abweichung setzt den adaptiven Plan sofort auf Schnellprüfung zurück",
    )

    immediate = runtime_for(mode="AUTO")
    active = update_vpd_control(immediate, now=3000)
    set_inside(immediate, temp=24.0, hum=63.0)
    recovered = update_vpd_control(immediate, now=3010)
    require(
        active["effect"]["next_evaluation_sec"] == 60
        and recovered["stage"] == "in_band"
        and recovered["direction"] is None
        and recovered["actions"]["dehumidifier"]["power"] is False,
        "Das Erreichen des VPD-Zielbands stoppt die Eskalation sofort und wartet nicht auf das Wirkungsfenster",
    )

    sluggish = runtime_for(mode="MONITOR")
    fan_states = sluggish.config["DEVICE_PARAMS"]["fan"]["control_states"]
    fan_states["env"]["controller"]["level"] = 80
    fan_states["env_standby"]["controller"]["level"] = 80
    update_vpd_control(sluggish, now=4000)
    heat = update_vpd_control(sluggish, now=4060)
    second_window = update_vpd_control(sluggish, now=4120)
    require(
        heat["stage"] == "heat"
        and heat["effect"]["window_sec"] == 60
        and second_window["stage"] == "heat"
        and second_window["strategy_progress"]["temperature"]["stall_windows"] == 1
        and second_window["effect"]["cadence"]["phase"] == "settling"
        and second_window["effect"]["window_sec"] == 120,
        "Eine träge unveränderte Heizstufe erhält nach der Schnellprüfung ein zweiminütiges zweites Wirkungsfenster",
    )

    capped = runtime_for(mode="MONITOR", temp=24.0, hum=63.0)
    capped.config["VPD_EFFECT_WINDOW_MIN"] = 2
    update_vpd_control(capped, now=5000)
    capped_stable = update_vpd_control(capped, now=5600)
    require(
        capped_stable["effect"]["cadence"]["phase"] == "stable"
        and capped_stable["effect"]["window_sec"] == 120
        and capped_stable["effect"]["max_window_sec"] == 120,
        "Der vorhandene Einstellwert bleibt die verbindliche Obergrenze des adaptiven Stabilfensters",
    )

    log_page = (ROOT / "templates" / "vpd_control_log.html").read_text(
        encoding="utf-8"
    )
    settings_page = (ROOT / "templates" / "settings.html").read_text(
        encoding="utf-8"
    )
    require(
        "cadence.label" in log_page
        and "nächste Stufenprüfung" in log_page
        and "Stabilprüfung max. (min)" in settings_page
        and "Adaptive Wirkungsprüfung" in settings_page,
        "Regellog und Einstellungen erklären den aktiven adaptiven Prüfmodus",
    )

    print("✅ Growstar 3.16.12 / VPD.CONTROL.6 vollständig geprüft")


if __name__ == "__main__":
    main()
