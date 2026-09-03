#!/usr/bin/env python3
"""Regression für intelligente, wirkungsgeprüfte VPD-Regelung."""

from copy import deepcopy
from pathlib import Path
import sys
import threading
import types


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# Das Produktionsprojekt verwendet requests für echte Shelly-Zugriffe. Dieser
# Test berechnet ausschließlich Shadow-Pläne und benötigt deshalb keinen
# Netzwerkclient. Ein minimaler Stub hält ihn auch in schlanken CI-Umgebungen
# ohne installierte Drittanbieterpakete ausführbar.
if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")

    class RequestException(Exception):
        pass

    requests_stub.RequestException = RequestException
    requests_stub.Timeout = RequestException
    requests_stub.ConnectionError = RequestException
    requests_stub.get = lambda *args, **kwargs: None
    requests_stub.post = lambda *args, **kwargs: None
    sys.modules["requests"] = requests_stub


from core.config import DEFAULT_CONFIG
from core.control import control_device
from core.helpers import calculate_vpd
from core.runtime import TentRuntime
from core.sensor_sources import apply_sensor_assignments, update_sensor_source
from core.safety import _device_dependencies
from core.state import create_runtime_state
from core.vpd import validate_vpd_environment_alignment
from core.vpd_control import update_vpd_control, vpd_manages_device


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def runtime_for(
    *,
    mode="AUTO",
    temp=24.0,
    hum=75.0,
    outside_temp=15.0,
    outside_hum=55.0,
    device_modes=None,
    outside=True,
    duplicate_source=False,
):
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg.update({
        "MIN_TEMP": 18.0,
        "MAX_TEMP": 30.0,
        "MIN_HUM": 0.0,
        "MAX_HUM": 90.0,
        "VPD_CONTROL_MODE": mode,
        "VPD_TARGET_DAY": 1.10,
        "VPD_TARGET_NIGHT": 0.90,
        "VPD_TOLERANCE": 0.05,
        "VPD_TEMP_MIN": 22.0,
        "VPD_TEMP_MAX": 26.0,
        "VPD_HUM_MIN": 50.0,
        "VPD_HUM_MAX": 80.0,
        "VPD_EFFECT_WINDOW_MIN": 5,
        "VPD_MIN_EFFECT_KPA": 0.03,
        "VPD_TEMP_STEP": 0.5,
        "VPD_FAN_STEP": 10,
        "DEVICE_MODES": device_modes or {
            "fan": "ENV",
            "heating": "ENV",
            "humidifier": "ENV",
            "dehumidifier": "ENV",
        },
        "DEVICE_PARAMS": {
            "fan": {
                "control_states": {
                    "env": {
                        "power": True,
                        "controller": {"level": 80},
                    },
                    "env_standby": {
                        "power": True,
                        "controller": {"level": 25},
                    },
                },
            },
        },
        "DEVICE_ENV_CONFIG": {
            "fan": {"standby_enabled": True},
        },
    })

    inside_id = "sensor:inside"
    outside_id = inside_id if duplicate_source else "sensor:outside"
    assignments = {
        "temperature": {"source_id": inside_id, "field": "temperature"},
        "humidity": {"source_id": inside_id, "field": "humidity"},
    }
    if outside:
        assignments.update({
            "outside_temperature": {
                "source_id": outside_id,
                "field": "temperature",
            },
            "outside_humidity": {
                "source_id": outside_id,
                "field": "humidity",
            },
        })
    cfg["SENSOR_ASSIGNMENTS"] = assignments

    state = create_runtime_state()
    state.current_profile = "TAG"
    state.live_state.update({
        "profile": "TAG",
        "temp": temp,
        "hum": hum,
        "vpd": calculate_vpd(temp, hum),
        "outside_temp": outside_temp if outside else None,
        "outside_hum": outside_hum if outside else None,
        "temp_target": 24.0,
        "temp_tol": 0.2,
    })

    return TentRuntime(
        tent_id="tent_vpd_test",
        name="VPD-Test",
        state=state,
        config=cfg,
        state_lock=threading.RLock(),
        control_enabled=False,
        shadow_enabled=True,
    )


def set_inside(runtime, *, temp, hum):
    with runtime.state_lock:
        runtime.state.live_state["temp"] = temp
        runtime.state.live_state["hum"] = hum
        runtime.state.live_state["vpd"] = calculate_vpd(temp, hum)


def main():
    cfg = deepcopy(DEFAULT_CONFIG)
    validated = validate_vpd_environment_alignment(cfg)
    require(
        validated["effect_window_sec"] == 300
        and validated["mode"] == "OFF",
        "VPD-Defaults sind gültig und bewerten Wirkung erst nach fünf Minuten",
    )

    incompatible = deepcopy(cfg)
    incompatible["VPD_CONTROL_MODE"] = "MONITOR"
    incompatible["VPD_TEMP_MAX"] = float(incompatible["MAX_TEMP"]) + 1
    try:
        validate_vpd_environment_alignment(incompatible)
    except ValueError:
        pass
    else:
        raise AssertionError("VPD-Fenster außerhalb der Schutzgrenze wurde akzeptiert")
    require(True, "VPD-Betriebsfenster bleibt innerhalb der Stations-Schutzgrenzen")

    prepared_off = deepcopy(incompatible)
    prepared_off["VPD_CONTROL_MODE"] = "OFF"
    validate_vpd_environment_alignment(prepared_off)
    require(
        True,
        "Vorbereitete VPD-Werte blockieren im ausgeschalteten Modus keine Klimaänderung",
    )

    sensor_runtime = runtime_for(mode="OFF")
    update_sensor_source(
        "sensor:inside",
        temperature=24.1,
        humidity=63.0,
    )
    update_sensor_source(
        "sensor:outside",
        temperature=15.2,
        humidity=54.0,
    )
    apply_sensor_assignments(runtime=sensor_runtime)
    require(
        sensor_runtime.state.live_state["outside_temp"] == 15.2
        and sensor_runtime.state.live_state["outside_hum"] == 54.0
        and sensor_runtime.state.live_state["outside_temp_source"]["source_id"]
        == "sensor:outside",
        "Optionale Außenquelle wird frisch und getrennt in die TentRuntime übernommen",
    )

    monitor = runtime_for(mode="MONITOR")
    monitor_plan = update_vpd_control(monitor, now=1000)
    require(
        monitor_plan["stage"] == "exhaust"
        and monitor_plan["takeover"] is False
        and not vpd_manages_device("fan", runtime=monitor),
        "Beobachten berechnet Abluft, übernimmt aber keinen Aktor",
    )

    missing = runtime_for(outside=False)
    missing_plan = update_vpd_control(missing, now=1000)
    require(
        missing_plan["fallback"] is True
        and missing_plan["stage"] == "waiting_sensors"
        and not vpd_manages_device("fan", runtime=missing),
        "Fehlendes Außenklima fällt ohne Blindsteuerung auf die klassische Regelung zurück",
    )
    missing.config["DEVICE_ENV_CONFIG"]["fan"].update({
        "use_temp": False,
        "use_hum": True,
    })
    require(
        _device_dependencies(missing, "fan", "ENV") == {"humidity"},
        "Der Sensor-Fallback behält auch im Safety-Supervisor die klassische ENV-Abhängigkeit",
    )

    duplicate = runtime_for(duplicate_source=True)
    duplicate_plan = update_vpd_control(duplicate, now=1000)
    require(
        duplicate_plan["fallback"] is True
        and "dieselbe Quelle" in duplicate_plan["reason"],
        "Dieselbe Quelle für innen und außen wird als unplausibel blockiert",
    )

    implausible = runtime_for()
    implausible.state.live_state["outside_hum"] = float("nan")
    implausible_plan = update_vpd_control(implausible, now=1000)
    require(
        implausible_plan["fallback"] is True
        and "unplausibel" in implausible_plan["reason"],
        "Nicht-endliche Außenwerte können niemals einen Aktorplan freigeben",
    )

    auto = runtime_for()
    first = update_vpd_control(auto, now=1000)
    require(
        first["stage"] == "exhaust"
        and first["actions"]["fan"]["power"] is True
        and first["actions"]["fan"]["controller"]["level"] == 25
        and first["actions"]["dehumidifier"]["power"] is False,
        "Zu niedriger VPD startet mit der kleinsten sinnvollen Abluftstufe",
    )
    control_device("fan", runtime=auto)
    require(
        auto.shadow_outputs.get("fan") is True,
        "Der VPD-Abluftplan läuft durch den bestehenden Shadow-/Aktorpfad",
    )
    require(
        _device_dependencies(auto, "fan", "ENV")
        == {"temperature", "humidity"},
        "Eine aktive AUTO-Übernahme benötigt im Safety-Supervisor beide Innenwerte",
    )

    second = update_vpd_control(auto, now=1301)
    require(
        second["stage"] == "heat"
        and second["effective_temp_target"] == 24.5
        and second["actions"]["dehumidifier"]["power"] is False,
        "Ohne Abluftwirkung wird nach fünf Minuten nur die Temperatur leicht angehoben",
    )

    third = update_vpd_control(auto, now=1602)
    require(
        third["stage"] == "dehumidify"
        and third["actions"]["dehumidifier"]["power"] is True,
        "Erst nach einer weiteren wirkungslosen Stufe wird der Entfeuchter angefordert",
    )
    control_device("dehumidifier", runtime=auto)
    require(
        auto.shadow_outputs.get("dehumidifier") is True,
        "Auch die letzte VPD-Stufe umgeht den bestehenden Aktorpfad nicht",
    )

    set_inside(auto, temp=24.0, hum=63.0)
    recovered = update_vpd_control(auto, now=1610)
    require(
        recovered["stage"] == "in_band"
        and recovered["actions"]["dehumidifier"]["power"] is False,
        "Im VPD-Zielband wird die Eskalation sofort sauber zurückgesetzt",
    )
    control_device("dehumidifier", runtime=auto)
    require(
        auto.shadow_outputs.get("dehumidifier") is False,
        "Nach Zielerreichung fordert derselbe sichere Pfad den Entfeuchter AUS an",
    )

    ramp_tracking = runtime_for(mode="AUTO", hum=63.0)
    ramp_tracking.state.live_state["climate_temp_target"] = 23.0
    ramp_tracking.state.live_state["temp_target"] = 23.0
    ramp_first = update_vpd_control(ramp_tracking, now=1000)
    ramp_tracking.state.live_state["climate_temp_target"] = 23.4
    ramp_tracking.state.live_state["temp_target"] = 23.4
    ramp_second = update_vpd_control(ramp_tracking, now=1001)
    require(
        ramp_first["effective_temp_target"] == 23.0
        and ramp_second["effective_temp_target"] == 23.4,
        "Ein VPD-Zyklus im Zielband folgt einer laufenden Temperatur-Rampe",
    )

    effective = runtime_for(mode="MONITOR")
    update_vpd_control(effective, now=1000)
    set_inside(effective, temp=24.0, hum=73.0)
    effective_plan = update_vpd_control(effective, now=1301)
    require(
        effective_plan["stage"] == "exhaust"
        and effective_plan["fan_level"] == 31,
        "Messbar wirksame Abluft wird behutsam erhöht statt vorschnell eskaliert",
    )

    wet_outside = runtime_for(outside_temp=24.0, outside_hum=90.0)
    wet_plan = update_vpd_control(wet_outside, now=1000)
    require(
        wet_plan["stage"] == "heat"
        and wet_plan["actions"]["fan"]["controller"].get("level") == 25,
        "Feuchtere Außenluft wird nicht als Entfeuchtungs-Hauptstufe missbraucht",
    )

    humidity_guard = runtime_for(temp=26.0, hum=66.0)
    humidity_guard.config.update({
        "VPD_TARGET_DAY": 0.95,
        "VPD_HUM_MAX": 65.0,
    })
    humidity_guard_plan = update_vpd_control(humidity_guard, now=1000)
    require(
        humidity_guard_plan["direction"] == "raise"
        and humidity_guard_plan["stage"] == "exhaust",
        "Die harte Feuchteobergrenze hat Vorrang vor einem widersprüchlichen VPD-Ziel",
    )

    high = runtime_for(hum=40.0)
    high_first = update_vpd_control(high, now=1000)
    high_second = update_vpd_control(high, now=1301)
    require(
        high_first["stage"] == "conserve"
        and high_first["actions"]["heating"]["power"] is False
        and high_second["stage"] == "humidify"
        and high_second["actions"]["humidifier"]["power"] is True,
        "Zu hoher VPD reduziert zuerst Wärme/Abluft und nutzt danach den Befeuchter",
    )

    off_devices = runtime_for(device_modes={
        "fan": "OFF",
        "heating": "OFF",
        "humidifier": "OFF",
        "dehumidifier": "OFF",
    })
    off_plan = update_vpd_control(off_devices, now=1000)
    require(
        off_plan["managed_devices"] == []
        and not vpd_manages_device("dehumidifier", runtime=off_devices),
        "AUTO übernimmt niemals Geräte außerhalb des ausdrücklich gewählten ENV-Modus",
    )

    control_source = (ROOT / "core/control.py").read_text(encoding="utf-8")
    loop_source = (ROOT / "threads/main.py").read_text(encoding="utf-8")
    safety_source = (ROOT / "core/safety.py").read_text(encoding="utf-8")
    require(
        "vpd_manages_device(device" in control_source
        and "update_vpd_control(runtime=rt" in loop_source
        and '{"temperature", "humidity"}' in safety_source,
        "Regelzyklus, ENV-Delegation und Safety-Abhängigkeiten sind vollständig verdrahtet",
    )

    settings_page = (ROOT / "templates/settings.html").read_text(encoding="utf-8")
    profile_page = (ROOT / "templates/profiles.html").read_text(encoding="utf-8")
    sensor_page = (ROOT / "templates/grow_control_sensors.html").read_text(encoding="utf-8")
    dashboard = (ROOT / "templates/grow_control.html").read_text(encoding="utf-8")
    require(
        'id="VPD_CONTROL_MODE"' in settings_page
        and "MONITOR" in settings_page
        and 'id="VPD_TARGET_DAY"' in profile_page
        and "outside_temperature" in sensor_page
        and 'id="vpd-control-summary"' in dashboard,
        "Einstellungen, Profile, Außensensoren und Dashboard zeigen die VPD-Funktion vollständig",
    )

    print("✅ Growstar 3.16.0 / VPD.CONTROL.1 vollständig geprüft")


if __name__ == "__main__":
    main()
