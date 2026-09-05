#!/usr/bin/env python3
"""Regression für VPD-Zielrampe und sichere Rampen-Neusynchronisierung."""

from copy import deepcopy
from pathlib import Path
import datetime
import sys
import threading
import time
import types


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
from core.config_update import apply_config_patch
from core.helpers import calculate_vpd
from core.runtime import TentRuntime
from core.state import create_runtime_state
import core.vpd as vpd_module
from core.vpd import calculate_vpd_schedule, validate_vpd_environment_alignment
from core.vpd_control import update_vpd_control


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def runtime_for(*, mode="AUTO", temp=24.0, hum=40.0):
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg.update({
        "DAY_START_MIN": 360,
        "NIGHT_START_MIN": 1320,
        "DAY_TEMP": 24.0,
        "NIGHT_TEMP": 21.0,
        "MIN_TEMP": 18.0,
        "MAX_TEMP": 30.0,
        "MIN_HUM": 0.0,
        "MAX_HUM": 90.0,
        "RAMP_ENABLED": 1,
        "RAMP_DURATION_MIN": 60,
        "VPD_CONTROL_MODE": mode,
        "VPD_TARGET_DAY": 1.10,
        "VPD_TARGET_NIGHT": 0.90,
        "VPD_TOLERANCE_DAY": 0.05,
        "VPD_TOLERANCE_NIGHT": 0.05,
        "VPD_TEMP_MIN_DAY": 22.0,
        "VPD_TEMP_MAX_DAY": 26.0,
        "VPD_HUM_MIN_DAY": 40.0,
        "VPD_HUM_MAX_DAY": 80.0,
        "VPD_TEMP_MIN_NIGHT": 20.0,
        "VPD_TEMP_MAX_NIGHT": 24.0,
        "VPD_HUM_MIN_NIGHT": 50.0,
        "VPD_HUM_MAX_NIGHT": 80.0,
        "DEVICE_MODES": {
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
        "SENSOR_ASSIGNMENTS": {
            "temperature": {
                "source_id": "sensor:inside",
                "field": "temperature",
            },
            "humidity": {
                "source_id": "sensor:inside",
                "field": "humidity",
            },
            "outside_temperature": {
                "source_id": "sensor:outside",
                "field": "temperature",
            },
            "outside_humidity": {
                "source_id": "sensor:outside",
                "field": "humidity",
            },
        },
    })

    state = create_runtime_state()
    state.current_profile = "TAG"
    state.live_state.update({
        "profile": "TAG",
        "temp": temp,
        "hum": hum,
        "vpd": calculate_vpd(temp, hum),
        "outside_temp": 15.0,
        "outside_hum": 55.0,
        "temp_target": 23.2,
        "climate_temp_target": 23.2,
        "temp_tol": 0.2,
    })

    return TentRuntime(
        tent_id="tent_vpd_ramp_test",
        name="VPD-Rampen-Test",
        state=state,
        config=cfg,
        state_lock=threading.RLock(),
        control_enabled=False,
        shadow_enabled=True,
    )


def main():
    schedule_runtime = runtime_for()
    settings = validate_vpd_environment_alignment(schedule_runtime.config)

    before, before_ramp = calculate_vpd_schedule(
        settings,
        schedule_runtime.config,
        "TAG",
        now_min=1259,
    )
    start, start_ramp = calculate_vpd_schedule(
        settings,
        schedule_runtime.config,
        "TAG",
        now_min=1260,
    )
    middle, middle_ramp = calculate_vpd_schedule(
        settings,
        schedule_runtime.config,
        "TAG",
        now_min=1290,
    )
    night, night_ramp = calculate_vpd_schedule(
        settings,
        schedule_runtime.config,
        "NACHT",
        now_min=1320,
    )

    require(
        before["target"] == 1.10
        and before_ramp["active"] is False
        and start["target"] == 1.10
        and start_ramp["kind"] == "evening"
        and round(middle["target"], 2) == 1.00
        and middle_ramp["progress"] == 0.5
        and night["target"] == 0.90
        and night_ramp["active"] is False,
        "Die Abendrampe führt stetig von 1,10 auf 0,90 kPa",
    )
    require(
        middle["temp_min"] == 21.0
        and middle["temp_max"] == 25.0
        and middle["hum_min"] == 45.0
        and middle["hum_max"] == 80.0,
        "Temperatur- und Feuchtefenster werden gemeinsam mit dem VPD-Ziel interpoliert",
    )

    morning, morning_ramp = calculate_vpd_schedule(
        settings,
        schedule_runtime.config,
        "TAG",
        now_min=390,
    )
    require(
        round(morning["target"], 2) == 1.00
        and morning_ramp["kind"] == "morning"
        and morning_ramp["progress"] == 0.5,
        "Die Morgenrampe führt spiegelbildlich vom Nacht- zum Tages-VPD",
    )

    original_minutes_now = vpd_module.minutes_now
    try:
        vpd_module.minutes_now = lambda: 1290

        monitor = runtime_for(mode="MONITOR")
        monitor_target_before = monitor.state.live_state["temp_target"]
        monitor_plan = update_vpd_control(monitor, now=1000)
        require(
            monitor_plan["target"] == 1.0
            and monitor_plan["ramp"]["kind"] == "evening"
            and monitor_plan["takeover"] is False
            and monitor.state.live_state["temp_target"] == monitor_target_before,
            "Beobachten simuliert die VPD-Rampe, verändert aber keinen klassischen Sollwert",
        )

        automatic = runtime_for(mode="AUTO")
        auto_plan = update_vpd_control(automatic, now=1000)
        require(
            auto_plan["stage"] == "humidify"
            and abs(auto_plan["preferred_temp_target"] - 22.95) < 0.02
            and abs(auto_plan["preferred_hum_target"] - 64.30) < 0.02
            and auto_plan["effective_temp_target"] == 24.0
            and automatic.state.live_state["temp_target"] == 24.0
            and 45.0 <= auto_plan["effective_hum_target"] <= 80.0
            and auto_plan["actions"]["humidifier"]["power"] is True
            and auto_plan["actions"]["heating"]["power"] is False,
            "AUTO behandelt während der Rampe zuerst die verbindliche Feuchte-Untergrenze",
        )
        require(
            auto_plan["range"] == {
                "temp_min": 21.0,
                "temp_max": 25.0,
                "hum_min": 45.0,
                "hum_max": 80.0,
            },
            "AUTO hält die Temperatur im aktuell gerampten Min-/Max-Fenster",
        )

        automatic.state.live_state["climate_temp_target"] = 28.0
        second_auto_plan = update_vpd_control(automatic, now=1001)
        require(
            second_auto_plan["effective_temp_target"]
            == auto_plan["effective_temp_target"],
            "Eine klassische Temperatur-Rampe kann den VPD-Sollwert nicht mehr verschieben",
        )

        dry_cold_air = runtime_for(mode="AUTO")
        dry_cold_air.state.live_state["outside_hum"] = 10.0
        dry_air_plan = update_vpd_control(dry_cold_air, now=1000)
        require(
            dry_air_plan["outside"]["cooling"] is True
            and dry_air_plan["outside"]["lowering"] is False
            and dry_air_plan["actions"]["fan"]["reason"] == "(VPD Grundlüftung)",
            "Kalte, aber zu trockene Außenluft wird nicht blind als VPD-Kühlhilfe genutzt",
        )
    finally:
        vpd_module.minutes_now = original_minutes_now

    incident = runtime_for(mode="OFF")
    now = time.time()
    current_minute = datetime.datetime.now().hour * 60 + datetime.datetime.now().minute
    incident.config["NIGHT_START_MIN"] = (current_minute + 60) % 1440
    incident.state.ramp_active = True
    incident.state.ramp_start_ts = now - 300
    incident.state.ramp_end_ts = now + 3600
    incident.state.ramp_start_temp = 24.0
    incident.state.ramp_target_temp = 21.0
    incident.state.last_ramp_trigger_day = datetime.date.today().isoformat()
    incident.state.last_ramp_trigger_type = "evening"
    incident.state.live_state["ramp_active"] = True
    incident.state.live_state["ramp_target"] = 21.0

    original_start_ts = incident.state.ramp_start_ts
    original_end_ts = incident.state.ramp_end_ts
    mode_result = apply_config_patch({
        "DAY_TEMP": incident.config["DAY_TEMP"],
        "NIGHT_TEMP": incident.config["NIGHT_TEMP"],
        "RAMP_DURATION_MIN": incident.config["RAMP_DURATION_MIN"],
        "VPD_CONTROL_MODE": "MONITOR",
    }, runtime=incident)
    require(
        mode_result["changed_keys"] == ["VPD_CONTROL_MODE"]
        and incident.state.ramp_start_ts == original_start_ts
        and incident.state.ramp_end_ts == original_end_ts
        and incident.state.ramp_target_temp == 21.0,
        "Ein VPD-Speichern fasst unveränderte Klima- und Rampenwerte nicht mehr an",
    )

    changed_result = apply_config_patch(
        {"NIGHT_TEMP": 20.5},
        runtime=incident,
    )
    require(
        changed_result["changed_keys"] == ["NIGHT_TEMP"]
        and incident.state.last_ramp_trigger_type == "evening"
        and incident.state.ramp_target_temp == 20.5
        and incident.state.ramp_end_ts > time.time(),
        "Eine echte Änderung behält bei laufender Abendrampe Richtung und Nachtziel",
    )

    print("✅ Growstar 3.16.4 / VPD.RAMP.1 vollständig geprüft")


if __name__ == "__main__":
    main()
