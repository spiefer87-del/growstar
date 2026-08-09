#!/usr/bin/env python3
"""Nicht-destruktiver Laufzeittest für Growstar Multi-Tent Phase 2.

Der Test erzeugt ausschließlich isolierte In-Memory-Runtimes. Es werden keine
Shellys geschaltet und keine Konfigurationsdateien gespeichert.
"""

import time
from copy import deepcopy

import core.context as ctx
import core.state as legacy_state

from core.config import config as legacy_config
from core.constants import SENSOR_TIMEOUT
from core.runtime import create_isolated_runtime, get_default_runtime
from core.sensor_sources import update_sensor_source, apply_sensor_assignments
from services.sensor import mark_stale_sensors
from core.control import update_temperature_setpoint, update_humidity_setpoint
from core.devices import get_device_mode, get_device_params
from core.ramp import start_ramp, stop_ramp
import core.profile as profile_module
import core.actuators as actuator_module


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    default_rt = get_default_runtime()

    require(default_rt.tent_id == "tent_1", "Default-Zelt ist nicht tent_1")
    require(default_rt.state is legacy_state, "Legacy-State wurde vom Default-Zelt getrennt")
    require(default_rt.config is legacy_config, "Legacy-Config wurde vom Default-Zelt getrennt")
    require(default_rt.state_lock is ctx.state_lock, "Default-State-Lock ist nicht kompatibel")

    common_assignment = {
        "temperature": {
            "source_id": "test:phase2",
            "field": "temperature",
            "label": "Phase-2-Test",
        },
        "humidity": {
            "source_id": "test:phase2",
            "field": "humidity",
            "label": "Phase-2-Test",
        },
    }

    rt_a = create_isolated_runtime(
        "tent_test_a",
        name="Testzelt A",
        config_data={
            "TEMP_OFFSET": 1.0,
            "HUM_OFFSET": -2.0,
            "DAY_TEMP": 25.0,
            "DAY_HUM": 58.0,
            "SENSOR_ASSIGNMENTS": common_assignment,
            "DEVICE_MODES": {
                "fan": "ON",
                "heating": {"mode": "ENV", "params": {"example": 1}},
            },
            "IP_FAN": "127.0.0.1",
            "RELAY_FAN": 0,
        },
    )

    rt_b = create_isolated_runtime(
        "tent_test_b",
        name="Testzelt B",
        config_data={
            "TEMP_OFFSET": -1.0,
            "HUM_OFFSET": 2.0,
            "DAY_TEMP": 23.0,
            "DAY_HUM": 64.0,
            "SENSOR_ASSIGNMENTS": common_assignment,
            "DEVICE_MODES": {"fan": "OFF"},
        },
    )

    require(rt_a.state is not rt_b.state, "Zelt-States teilen dieselbe Instanz")
    require(rt_a.config is not rt_b.config, "Zelt-Configs teilen dieselbe Instanz")
    require(rt_a.state_lock is not rt_b.state_lock, "Zelt-Locks teilen dieselbe Instanz")

    source_id = "test:phase2"
    with ctx.state_lock:
        previous_source = legacy_state.live_state.setdefault(
            "sensor_sources", {}
        ).get(source_id)
        previous_source = deepcopy(previous_source)

    previous_default_temp = legacy_state.live_state.get("temp")
    previous_default_hum = legacy_state.live_state.get("hum")
    previous_profile_minutes = profile_module.minutes_now
    previous_switch = actuator_module.switch_shelly

    try:
        update_sensor_source(
            source_id,
            label="Phase-2-Test",
            source_type="test",
            temperature=25.0,
            humidity=60.0,
        )

        require(apply_sensor_assignments(runtime=rt_a), "Sensoren wurden A nicht zugewiesen")
        require(apply_sensor_assignments(runtime=rt_b), "Sensoren wurden B nicht zugewiesen")

        require(rt_a.state.live_state["temp"] == 26.0, "TEMP_OFFSET A falsch")
        require(rt_b.state.live_state["temp"] == 24.0, "TEMP_OFFSET B falsch")
        require(rt_a.state.live_state["hum"] == 58.0, "HUM_OFFSET A falsch")
        require(rt_b.state.live_state["hum"] == 62.0, "HUM_OFFSET B falsch")

        require(
            legacy_state.live_state.get("temp") == previous_default_temp,
            "Isoliertes Zelt A/B hat den Default-Temperaturstate verändert",
        )
        require(
            legacy_state.live_state.get("hum") == previous_default_hum,
            "Isoliertes Zelt A/B hat den Default-Feuchtestate verändert",
        )

        # Profil deterministisch auf TAG setzen.
        profile_module.minutes_now = lambda: 600
        update_temperature_setpoint(runtime=rt_a)
        update_humidity_setpoint(runtime=rt_a)
        update_temperature_setpoint(runtime=rt_b)
        update_humidity_setpoint(runtime=rt_b)

        require(rt_a.state.live_state["temp_target"] == 25.0, "Solltemperatur A falsch")
        require(rt_b.state.live_state["temp_target"] == 23.0, "Solltemperatur B falsch")
        require(rt_a.state.live_state["hum_target"] == 58.0, "Sollfeuchte A falsch")
        require(rt_b.state.live_state["hum_target"] == 64.0, "Sollfeuchte B falsch")

        # Rampenstate muss zeltweise getrennt bleiben.
        start_ramp(26.0, 25.0, 700, runtime=rt_a)
        require(rt_a.state.ramp_active is True, "Rampe A wurde nicht gestartet")
        require(rt_b.state.ramp_active is False, "Rampe A hat Zelt B beeinflusst")
        stop_ramp(runtime=rt_a)

        # DEVICE_MODES muss altes Dict- und neues String-Schema akzeptieren.
        require(get_device_mode("fan", runtime=rt_a) == "ON", "String-Gerätemodus falsch")
        require(get_device_mode("heating", runtime=rt_a) == "ENV", "Dict-Gerätemodus falsch")
        require(
            get_device_params("heating", runtime=rt_a).get("example") == 1,
            "Legacy-Geräteparameter wurden nicht gelesen",
        )

        # Aktorpfad ohne Netzwerkzugriff testen.
        actuator_module.switch_shelly = lambda *args, **kwargs: True
        actuator_module.set_fan(True, runtime=rt_a)
        require(rt_a.state.fan_on is True, "Aktorstate A wurde nicht gesetzt")
        require(rt_b.state.fan_on is False, "Aktorstate A hat Zelt B beeinflusst")

        # Stale-Test: echter Source-last_seen muss erhalten bleiben und die
        # Safety-Logik muss alte Messwerte aus dem Zeltstate entfernen.
        stale_ts = time.time() - SENSOR_TIMEOUT - 5
        with ctx.state_lock:
            legacy_state.live_state["sensor_sources"][source_id]["last_seen"] = stale_ts

        old_a_temp = rt_a.state.live_state["temp"]
        apply_sensor_assignments(runtime=rt_a)
        require(
            rt_a.state.live_state["temp"] == old_a_temp,
            "Stale Quelle wurde vor Safety-Prüfung erneut als neuer Messwert übernommen",
        )
        require(
            abs(rt_a.state.last_ds_time - stale_ts) < 0.01,
            "Source-last_seen wurde nicht als Sensorzeit übernommen",
        )

        # Kein realer Shelly-Aufruf: fan/heating werden im Test ebenfalls über
        # den oben gepatchten switch_shelly-Pfad sicher abgefangen.
        mark_stale_sensors(runtime=rt_a)
        require(rt_a.state.temp_stale is True, "Temperatur-Stale wurde nicht erkannt")
        require(rt_a.state.hum_stale is True, "Feuchte-Stale wurde nicht erkannt")
        require(rt_a.state.live_state["temp"] is None, "Stale Temperatur blieb live")
        require(rt_a.state.live_state["hum"] is None, "Stale Feuchte blieb live")

    finally:
        profile_module.minutes_now = previous_profile_minutes
        actuator_module.switch_shelly = previous_switch

        with ctx.state_lock:
            sources = legacy_state.live_state.setdefault("sensor_sources", {})
            if previous_source is None:
                sources.pop(source_id, None)
            else:
                sources[source_id] = previous_source

    print("✅ Phase 2 Runtime-Kompatibilität OK")
    print("✅ State/Config/Locks pro Zelt getrennt")
    print("✅ Sensor-Zuweisung pro Zelt getrennt")
    print("✅ Sollwerte/Rampe/Aktoren pro Zelt getrennt")
    print("✅ Sensor-last_seen / Stale-Failsafe OK")


if __name__ == "__main__":
    main()
