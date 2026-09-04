#!/usr/bin/env python3
"""Regression für Growstar 3.16.10 / VPD.CONTROL.4."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
REGRESSION = ROOT / "tests" / "regression"
for path in (ROOT, REGRESSION):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


from check_vpd_intelligent_control import runtime_for
from core.control import update_humidity_setpoint
from core.vpd import reset_vpd_control
from core.vpd_control import update_vpd_control


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def coupled_runtime(*, mode="AUTO"):
    runtime = runtime_for(
        mode=mode,
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
        "DAY_HUM": 65.0,
        "DAY_HUM_TOL": 3.0,
        "VPD_TEMP_MIN_DAY": 20.0,
        "VPD_TEMP_MAX_DAY": 26.0,
        "VPD_HUM_MIN_DAY": 50.0,
        "VPD_HUM_MAX_DAY": 60.0,
    })
    fan_states = runtime.config["DEVICE_PARAMS"]["fan"]["control_states"]
    fan_states["env"]["controller"]["level"] = 75
    fan_states["env_standby"]["controller"]["level"] = 75
    update_humidity_setpoint(runtime=runtime)
    runtime.state.live_state["climate_temp_target"] = 24.0
    runtime.state.live_state["temp_target"] = 24.0
    return runtime


def main():
    automatic = coupled_runtime()
    first = update_vpd_control(automatic, now=1000)
    setpoints = first["setpoints"]

    require(
        setpoints["at_temp_max"]["hum"] == 60.0
        and abs(setpoints["at_temp_max"]["calculated_hum"] - 67.28) < 0.02
        and setpoints["at_temp_max"]["within_humidity_range"] is False,
        "Auch bei 26 Grad bleibt der Sollwert auf 60 Prozent begrenzt und der höhere Rechenwert nur Diagnose",
    )
    require(
        abs(setpoints["temp"] - 23.9) < 0.02
        and setpoints["hum"] == 60.0
        and abs(setpoints["calculated_hum"] - 62.91) < 0.02
        and abs(setpoints["vpd"] - 1.10) < 0.001,
        "Der Live-Feuchtesollwert überschreitet trotz höherem VPD-Rechenwert niemals die konfigurierte Obergrenze",
    )
    require(
        abs(automatic.state.live_state["temp_target"] - setpoints["temp"]) < 0.01
        and abs(automatic.state.live_state["hum_target"] - setpoints["hum"]) < 0.01
        and abs(automatic.state.live_state["vpd_hum_target"] - setpoints["hum"]) < 0.01,
        "VPD-AUTO veröffentlicht Temperatur- und Feuchtesollwert gemeinsam im Live-State",
    )
    require(
        "VPD ist gleichzeitig zu niedrig" in first["reason"]
        and "verbindlichen Obergrenze" in first["reason"]
        and "26.0 °C" in setpoints["explanation"]
        and "67.3 %" in setpoints["explanation"]
        and "überschreibt die konfigurierte Feuchtegrenze nicht" in setpoints["explanation"],
        "Regellog trennt den mathematischen Rechenwert eindeutig vom verbindlichen Feuchtesollwert",
    )

    dynamic = runtime_for(mode="AUTO", temp=24.0, hum=75.0)
    dynamic_states = dynamic.config["DEVICE_PARAMS"]["fan"]["control_states"]
    dynamic_states["env"]["controller"]["level"] = 75
    dynamic_states["env_standby"]["controller"]["level"] = 75
    dynamic_first = update_vpd_control(dynamic, now=1000)
    dynamic_second = update_vpd_control(dynamic, now=1301)
    require(
        dynamic_first["setpoints"]["temp"] == 24.0
        and abs(dynamic_first["setpoints"]["hum"] - 63.14) < 0.02
        and dynamic_second["setpoints"]["temp"] == 24.5
        and abs(dynamic_second["setpoints"]["hum"] - 64.24) < 0.02,
        "Jede neue VPD-Temperaturstufe berechnet den zugehörigen Feuchtesollwert live neu",
    )

    plans = [first]
    now = 1000
    for _ in range(3):
        now += 301
        plans.append(update_vpd_control(automatic, now=now))
    require(
        [plan["fan_level"] for plan in plans] == [75, 85, 95, 100],
        "Die Spider-Farmer-Abluft staffelt weiterhin lückenlos von 75 bis 100 Prozent",
    )

    now += 301
    heat = update_vpd_control(automatic, now=now)
    require(
        heat["stage"] == "heat"
        and heat["effective_temp_target"] == 24.4
        and heat["strategy_progress"]["fan"]["complete"] is True
        and heat["actions"]["fan"]["controller"]["level"] == 100
        and heat["actions"]["heating"]["power"] is True,
        "Nach vollständig geprüfter Abluft wird die echte Temperaturreserve genutzt und Stufe 100 beibehalten",
    )

    now += 301
    held = update_vpd_control(automatic, now=now)
    require(
        held["stage"] == "heat"
        and held["actions"]["fan"]["controller"]["level"] == 100
        and held["actions"]["heating"]["power"] is True,
        "Die Heizprüfung hält die maximale Abluft und fällt weder auf LIMITED noch auf die Grundlüftung zurück",
    )

    automatic.state.live_state["outside_temp"] = 26.0
    automatic.state.live_state["outside_hum"] = 90.0
    unsuitable = update_vpd_control(automatic, now=now + 1)
    require(
        unsuitable["outside"]["drying"] is False
        and unsuitable["actions"]["fan"]["controller"]["level"] == 75
        and "Grundlüftung" in unsuitable["actions"]["fan"]["reason"],
        "Erst ungeeignete Außenluft gibt die VPD-Maximalstufe kontrolliert an Standby zurück",
    )

    monitor = coupled_runtime(mode="MONITOR")
    monitor_plan = update_vpd_control(monitor, now=1000)
    require(
        monitor_plan["setpoints"]["hum"] == 60.0
        and abs(monitor_plan["setpoints"]["calculated_hum"] - 62.91) < 0.02
        and monitor.state.live_state["hum_target"] == 65.0,
        "Beobachten zeigt den begrenzten VPD-Sollwert, ersetzt aber keinen klassischen Live-Sollwert",
    )

    fallback = coupled_runtime()
    update_vpd_control(fallback, now=1000)
    fallback.state.live_state["outside_temp"] = None
    fallback.state.live_state["outside_hum"] = None
    fallback_plan = update_vpd_control(fallback, now=1001)
    require(
        fallback_plan["fallback"] is True
        and fallback.state.live_state["temp_target"] == 24.0
        and fallback.state.live_state["hum_target"] == 65.0
        and "vpd_hum_target" not in fallback.state.live_state,
        "Sensor-Fallback entfernt VPD-Sollwerte und stellt die klassische Regelbasis wieder her",
    )

    reset_vpd_control(automatic, reason="Regression")
    require(
        automatic.state.live_state["temp_target"] == 24.0
        and automatic.state.live_state["hum_target"] == 65.0
        and "vpd_hum_target" not in automatic.state.live_state,
        "VPD-Reset stellt die getrennt erhaltenen klassischen Sollwerte sofort wieder her",
    )

    automatic = coupled_runtime()
    automatic.config["DAY_HUM"] = 42.0
    automatic.config["DAY_HUM_TOL"] = 19.0
    changed_classic = update_vpd_control(automatic, now=1000)
    require(
        changed_classic["setpoints"]["temp"] == first["setpoints"]["temp"]
        and changed_classic["setpoints"]["hum"] == first["setpoints"]["hum"]
        and changed_classic["actions"]["fan"]["controller"]["level"]
        == first["actions"]["fan"]["controller"]["level"],
        "Klassischer Feuchtesollwert und klassische Regeltoleranz beeinflussen VPD-AUTO nicht",
    )

    dashboard = (ROOT / "templates" / "grow_control.html").read_text(encoding="utf-8")
    log_page = (ROOT / "templates" / "vpd_control_log.html").read_text(encoding="utf-8")
    require(
        'id="temp-target-row"' in dashboard
        and 'id="hum-target-row"' in dashboard
        and 'id="vpd-log-setpoints"' in log_page
        and 'id="vpd-log-coupling"' in log_page,
        "Dashboard und Regellog besitzen die Anzeigen für gekoppelte Live-Sollwerte",
    )

    print("✅ Growstar 3.16.10 / VPD.CONTROL.4 vollständig geprüft")


if __name__ == "__main__":
    main()
