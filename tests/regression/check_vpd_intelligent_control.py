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


from core.config import DEFAULT_CONFIG, migrate_vpd_phase_config
from core.config_update import apply_config_patch
from core.control import control_device
from core.helpers import calculate_vpd
from core.profile import (
    PROFILE_SETTING_KEYS,
    VPD_PROFILE_SETTING_KEYS,
    normalize_profile_settings,
    profile_settings_from_config,
)
from core.runtime import TentRuntime
from core.sensor_sources import apply_sensor_assignments, update_sensor_source
from core.safety import _device_dependencies
from core.state import create_runtime_state
from core.tent_config import _with_defaults
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
        "VPD_TOLERANCE_DAY": 0.05,
        "VPD_TOLERANCE_NIGHT": 0.05,
        "VPD_TEMP_MIN_DAY": 22.0,
        "VPD_TEMP_MAX_DAY": 26.0,
        "VPD_HUM_MIN_DAY": 50.0,
        "VPD_HUM_MAX_DAY": 80.0,
        "VPD_TEMP_MIN_NIGHT": 22.0,
        "VPD_TEMP_MAX_NIGHT": 26.0,
        "VPD_HUM_MIN_NIGHT": 50.0,
        "VPD_HUM_MAX_NIGHT": 80.0,
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

    legacy_values = {
        "VPD_TOLERANCE": 0.08,
        "VPD_TEMP_MIN": 21.5,
        "VPD_TEMP_MAX": 27.5,
        "VPD_HUM_MIN": 44.0,
        "VPD_HUM_MAX": 76.0,
    }
    migrated_values = migrate_vpd_phase_config(
        deepcopy(legacy_values),
        remove_legacy=True,
    )
    require(
        migrated_values["VPD_TOLERANCE_DAY"] == 0.08
        and migrated_values["VPD_TOLERANCE_NIGHT"] == 0.08
        and migrated_values["VPD_TEMP_MIN_DAY"] == 21.5
        and migrated_values["VPD_TEMP_MIN_NIGHT"] == 21.5
        and migrated_values["VPD_HUM_MAX_DAY"] == 76.0
        and migrated_values["VPD_HUM_MAX_NIGHT"] == 76.0
        and not set(legacy_values).intersection(migrated_values),
        "Gemeinsame VPD-Werte aus 3.16.0 werden verlustfrei auf Tag und Nacht gespiegelt",
    )

    legacy_cfg = deepcopy(DEFAULT_CONFIG)
    for key in VPD_PROFILE_SETTING_KEYS:
        if key not in {"VPD_TARGET_DAY", "VPD_TARGET_NIGHT"}:
            legacy_cfg.pop(key, None)
    legacy_cfg.update(legacy_values)
    legacy_validated = validate_vpd_environment_alignment(legacy_cfg)
    require(
        legacy_validated["phases"]["TAG"]["temp_min"] == 21.5
        and legacy_validated["phases"]["NACHT"]["hum_max"] == 76.0,
        "Der Regler validiert auch eine noch nicht persistierte 3.16.0-Konfiguration",
    )

    migrated_tent_config = _with_defaults(legacy_values)
    require(
        migrated_tent_config["VPD_TOLERANCE_DAY"] == 0.08
        and migrated_tent_config["VPD_TOLERANCE_NIGHT"] == 0.08
        and migrated_tent_config["VPD_HUM_MAX_DAY"] == 76.0
        and migrated_tent_config["VPD_HUM_MAX_NIGHT"] == 76.0
        and migrated_tent_config["OUTSIDE_TEMP_OFFSET"] == 0.0
        and migrated_tent_config["OUTSIDE_HUM_OFFSET"] == 0.0,
        "Zusätzliche Zelte übernehmen VPD-Werte und sichere Außen-Offset-Defaults",
    )

    incompatible = deepcopy(cfg)
    incompatible["VPD_CONTROL_MODE"] = "MONITOR"
    incompatible["VPD_TEMP_MAX_DAY"] = float(incompatible["MAX_TEMP"]) + 1
    try:
        validate_vpd_environment_alignment(incompatible)
    except ValueError:
        pass
    else:
        raise AssertionError("VPD-Fenster außerhalb der Schutzgrenze wurde akzeptiert")
    require(True, "VPD-Betriebsfenster bleibt innerhalb der Stations-Schutzgrenzen")

    incompatible_night = deepcopy(cfg)
    incompatible_night["VPD_CONTROL_MODE"] = "AUTO"
    incompatible_night["VPD_HUM_MAX_NIGHT"] = 80.0
    try:
        validate_vpd_environment_alignment(incompatible_night)
    except ValueError as exc:
        require(
            "Nacht" in str(exc),
            "Eine verletzte Nachtgrenze wird phasengenau gemeldet",
        )
    else:
        raise AssertionError("VPD-Nachtfenster außerhalb der Schutzgrenze wurde akzeptiert")

    prepared_off = deepcopy(incompatible)
    prepared_off["VPD_CONTROL_MODE"] = "OFF"
    validate_vpd_environment_alignment(prepared_off)
    require(
        True,
        "Vorbereitete VPD-Werte blockieren im ausgeschalteten Modus keine Klimaänderung",
    )

    profile_base = {
        key: deepcopy(DEFAULT_CONFIG[key])
        for key in PROFILE_SETTING_KEYS
        if key not in VPD_PROFILE_SETTING_KEYS
    }
    legacy_profile = {
        **profile_base,
        "VPD_TARGET_DAY": 1.15,
        "VPD_TARGET_NIGHT": 0.85,
        **legacy_values,
    }
    normalized_legacy_profile = normalize_profile_settings(legacy_profile)
    require(
        normalized_legacy_profile["VPD_TOLERANCE_DAY"] == 0.08
        and normalized_legacy_profile["VPD_TOLERANCE_NIGHT"] == 0.08
        and normalized_legacy_profile["VPD_TEMP_MAX_DAY"] == 27.5
        and normalized_legacy_profile["VPD_TEMP_MAX_NIGHT"] == 27.5
        and not set(legacy_values).intersection(normalized_legacy_profile),
        "Gespeicherte 3.16.0-Profile behalten ihr gemeinsames Fenster in beiden Phasen",
    )

    legacy_station_snapshot = profile_settings_from_config(legacy_profile)
    require(
        legacy_station_snapshot["VPD_TOLERANCE_DAY"] == 0.08
        and legacy_station_snapshot["VPD_TOLERANCE_NIGHT"] == 0.08
        and legacy_station_snapshot["VPD_HUM_MIN_DAY"] == 44.0
        and legacy_station_snapshot["VPD_HUM_MIN_NIGHT"] == 44.0,
        "Aktuelle Stationswerte lassen sich nach der Migration vollständig ins Profil kopieren",
    )

    pre_vpd_profile = deepcopy(profile_base)
    pre_vpd_profile.update({
        "DAY_TEMP": 26.0,
        "DAY_TEMP_TOL": 1.0,
        "DAY_HUM": 58.0,
        "DAY_HUM_TOL": 4.0,
        "NIGHT_TEMP": 20.0,
        "NIGHT_TEMP_TOL": 2.0,
        "NIGHT_HUM": 68.0,
        "NIGHT_HUM_TOL": 6.0,
    })
    normalized_pre_vpd_profile = normalize_profile_settings(pre_vpd_profile)
    require(
        normalized_pre_vpd_profile["VPD_TEMP_MIN_DAY"] == 25.0
        and normalized_pre_vpd_profile["VPD_TEMP_MAX_DAY"] == 27.0
        and normalized_pre_vpd_profile["VPD_HUM_MIN_DAY"] == 54.0
        and normalized_pre_vpd_profile["VPD_TEMP_MIN_NIGHT"] == 18.0
        and normalized_pre_vpd_profile["VPD_TEMP_MAX_NIGHT"] == 22.0
        and normalized_pre_vpd_profile["VPD_HUM_MIN_NIGHT"] == 62.0,
        "Profile von vor 3.16 erhalten getrennte, aus Tag/Nacht abgeleitete Fenster",
    )

    sensor_runtime = runtime_for(mode="OFF")
    sensor_runtime.config["OUTSIDE_TEMP_OFFSET"] = 0.6
    sensor_runtime.config["OUTSIDE_HUM_OFFSET"] = -2.0
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
        sensor_runtime.state.live_state["outside_temp_raw"] == 15.2
        and round(sensor_runtime.state.live_state["outside_temp"], 1) == 15.8
        and sensor_runtime.state.live_state["outside_hum_raw"] == 54.0
        and sensor_runtime.state.live_state["outside_hum"] == 52.0
        and sensor_runtime.state.live_state["outside_temp_source"]["source_id"]
        == "sensor:outside",
        "Außenquelle wird frisch, RAW und separat korrigiert in die TentRuntime übernommen",
    )
    sensor_runtime.config["VPD_CONTROL_MODE"] = "MONITOR"
    corrected_outside_plan = update_vpd_control(sensor_runtime, now=1000)
    require(
        corrected_outside_plan["outside"]["temp"] == 15.8
        and corrected_outside_plan["outside"]["hum"] == 52.0,
        "VPD-Wirkungsprognose verwendet ausschließlich die korrigierten Außenwerte",
    )

    sensor_runtime.config["SENSOR_ASSIGNMENTS"].pop("outside_temperature")
    sensor_runtime.config["SENSOR_ASSIGNMENTS"].pop("outside_humidity")
    apply_sensor_assignments(runtime=sensor_runtime)
    require(
        sensor_runtime.state.live_state["outside_temp_raw"] is None
        and sensor_runtime.state.live_state["outside_temp"] is None
        and sensor_runtime.state.live_state["outside_hum_raw"] is None
        and sensor_runtime.state.live_state["outside_hum"] is None,
        "Entfernte Außenquellen löschen RAW- und korrigierte Werte gemeinsam",
    )

    stale_browser_runtime = runtime_for(mode="OFF")
    stale_browser_result = apply_config_patch(
        legacy_values,
        runtime=stale_browser_runtime,
    )
    require(
        stale_browser_runtime.config["VPD_TEMP_MIN_DAY"] == 21.5
        and stale_browser_runtime.config["VPD_TEMP_MIN_NIGHT"] == 21.5
        and stale_browser_runtime.config["VPD_HUM_MAX_DAY"] == 76.0
        and stale_browser_runtime.config["VPD_HUM_MAX_NIGHT"] == 76.0
        and not set(legacy_values).intersection(stale_browser_runtime.config)
        and "VPD_TOLERANCE_DAY" in stale_browser_result["changed_keys"]
        and "VPD_TOLERANCE_NIGHT" in stale_browser_result["changed_keys"],
        "Eine noch geöffnete 3.16.0-Webseite speichert sicher in beide Phasen",
    )

    monitor = runtime_for(mode="MONITOR")
    monitor_plan = update_vpd_control(monitor, now=1000)
    require(
        monitor_plan["stage"] == "exhaust"
        and monitor_plan["takeover"] is False
        and not vpd_manages_device("fan", runtime=monitor),
        "Beobachten berechnet Abluft, übernimmt aber keinen Aktor",
    )

    tolerance_runtime = runtime_for(mode="MONITOR", temp=24.0, hum=60.0)
    tolerance_runtime.config.update({
        "VPD_TARGET_NIGHT": 1.10,
        "VPD_TOLERANCE_NIGHT": 0.20,
        "VPD_TEMP_MIN_NIGHT": 19.0,
        "VPD_TEMP_MAX_NIGHT": 25.0,
        "VPD_HUM_MIN_NIGHT": 55.0,
        "VPD_HUM_MAX_NIGHT": 85.0,
    })
    day_tolerance_plan = update_vpd_control(tolerance_runtime, now=1000)
    tolerance_runtime.state.current_profile = "NACHT"
    tolerance_runtime.state.live_state["profile"] = "NACHT"
    night_tolerance_plan = update_vpd_control(tolerance_runtime, now=1001)
    require(
        day_tolerance_plan["direction"] == "lower"
        and day_tolerance_plan["tolerance"] == 0.05
        and night_tolerance_plan["stage"] == "in_band"
        and night_tolerance_plan["tolerance"] == 0.20
        and night_tolerance_plan["range"] == {
            "temp_min": 19.0,
            "temp_max": 25.0,
            "hum_min": 55.0,
            "hum_max": 85.0,
        },
        "Tag und Nacht verwenden ihre eigene Toleranz und ihr eigenes Klimafenster",
    )

    phase_reset = runtime_for(mode="MONITOR")
    first_day_stage = update_vpd_control(phase_reset, now=1000)
    escalated_day_stage = update_vpd_control(phase_reset, now=1301)
    phase_reset.config.update({
        "VPD_TOLERANCE_NIGHT": 0.05,
        "VPD_TEMP_MIN_NIGHT": 19.0,
        "VPD_TEMP_MAX_NIGHT": 25.0,
        "VPD_HUM_MIN_NIGHT": 55.0,
        "VPD_HUM_MAX_NIGHT": 85.0,
    })
    phase_reset.state.current_profile = "NACHT"
    phase_reset.state.live_state["profile"] = "NACHT"
    first_night_stage = update_vpd_control(phase_reset, now=1302)
    require(
        first_day_stage["stage"] == "exhaust"
        and escalated_day_stage["stage"] == "heat"
        and first_night_stage["profile"] == "NACHT"
        and first_night_stage["stage"] == "exhaust"
        and first_night_stage["effect"]["next_evaluation_sec"] == 300,
        "Der Tag-/Nachtwechsel startet die Wirkungsprüfung mit dem neuen Fenster frisch",
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
        ramp_first["effective_temp_target"] == 24.0
        and ramp_second["effective_temp_target"] == 24.0,
        "Der VPD-Regler übernimmt keine klassische Temperatur-Rampe mehr als Regelbasis",
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
        "VPD_HUM_MAX_DAY": 65.0,
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
        high_first["stage"] == "cool"
        and high_first["actions"]["heating"]["power"] is False
        and high_second["stage"] == "humidify"
        and high_second["actions"]["humidifier"]["power"] is True,
        "Zu hoher VPD senkt zuerst das Temperaturziel und nutzt danach den Befeuchter",
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
        and 'id="VPD_TOLERANCE_DAY"' in settings_page
        and 'id="VPD_TEMP_MIN_NIGHT"' in settings_page
        and 'id="VPD_TARGET_DAY"' in profile_page
        and 'id="VPD_TOLERANCE_NIGHT"' in profile_page
        and 'id="VPD_HUM_MAX_DAY"' in profile_page
        and "outside_temperature" in sensor_page
        and 'id="vpd-control-summary"' in dashboard,
        "Einstellungen, Profile, Außensensoren und Dashboard zeigen beide VPD-Phasen vollständig",
    )

    print("✅ Growstar 3.16.1 / VPD.CONTROL.2 vollständig geprüft")


if __name__ == "__main__":
    main()
