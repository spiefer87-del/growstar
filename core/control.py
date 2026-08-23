# core/control.py

import time

from core.runtime import resolve_runtime
from core.profile import get_profile
from core.ramp import get_ramped_target
from core.helpers import minutes_now, in_time_window
from core.actuators import (
    set_device,
    set_heating,
    set_fan,
    set_vent,
)
from core.controller_states import (
    apply_device_state,
    resolve_control_state,
)
from core.devices import (
    get_device_mode,
    get_device_params,
)


# =========================================
# 🌡️ REGELLOGIK
# =========================================

def update_humidity_setpoint(runtime=None):
    rt = resolve_runtime(runtime)
    cfg = rt.config
    st = rt.state

    profile = get_profile(runtime=rt)

    if profile == "TAG":
        base, tol = cfg["DAY_HUM"], cfg["DAY_HUM_TOL"]
    else:
        base, tol = cfg["NIGHT_HUM"], cfg["NIGHT_HUM_TOL"]

    st.live_state["hum_target"] = base
    st.live_state["hum_tol"] = tol


def update_temperature_setpoint(runtime=None):
    rt = resolve_runtime(runtime)
    cfg = rt.config
    st = rt.state

    profile = get_profile(runtime=rt)

    if profile == "TAG":
        base = float(cfg["DAY_TEMP"])
        tol = float(cfg["DAY_TEMP_TOL"])
    else:
        base = float(cfg["NIGHT_TEMP"])
        tol = float(cfg["NIGHT_TEMP_TOL"])

    target = base

    if st.ramp_active:
        ramp_target = get_ramped_target(runtime=rt)
        if ramp_target is not None:
            target = ramp_target

    st.live_state["temp_target"] = target
    st.live_state["temp_tol"] = tol

    print(
        f"{time.strftime('%H:%M:%S')} "
        f"[{rt.tent_id}] "
        f"({minutes_now()} min) | "
        f"profile={profile} | "
        f"ramp={st.ramp_active} | "
        f"ramp_target={st.ramp_target_temp} | "
        f"base={base:.2f} | "
        f"target={target:.2f}"
    )


def evaluate_env_conditions(device, runtime=None):
    rt = resolve_runtime(runtime)
    cfg = rt.config
    st = rt.state

    env_cfg = cfg.get("DEVICE_ENV_CONFIG", {}).get(device, {})
    if not env_cfg:
        return False

    use_temp = env_cfg.get("use_temp", False)
    use_hum = env_cfg.get("use_hum", False)
    logic = env_cfg.get("logic", "OR")
    direction = env_cfg.get("direction", "HIGH")

    results = []

    if use_temp:
        temp = st.live_state.get("temp")
        target = st.live_state.get("temp_target")
        tol = st.live_state.get("temp_tol")

        if None not in (temp, target, tol):
            if direction == "HIGH":
                results.append(temp > (target + tol))
            else:
                results.append(temp < (target - tol))

    if use_hum:
        hum = st.live_state.get("hum")
        target = st.live_state.get("hum_target")
        tol = st.live_state.get("hum_tol")

        if None not in (hum, target, tol):
            if direction == "HIGH":
                results.append(hum > (target + tol))
            else:
                results.append(hum < (target - tol))

    if not results:
        return False

    if logic == "AND":
        return all(results)

    return any(results)


def control_device(device, runtime=None):
    rt = resolve_runtime(runtime)

    mode = get_device_mode(device, runtime=rt)
    params = get_device_params(device, runtime=rt)

    now_min = minutes_now()

    if mode == "OFF":
        apply_device_state(
            device,
            resolve_control_state(params, "off"),
            runtime=rt,
        )
        return

    if mode == "ON":
        apply_device_state(
            device,
            resolve_control_state(params, "on"),
            runtime=rt,
        )
        return

    if mode == "TIME":
        start = int(params.get("start_min", 0))
        end = int(params.get("end_min", 0))
        should_run = in_time_window(now_min, start, end)

        state_name = "on" if should_run else "off"
        apply_device_state(
            device,
            resolve_control_state(params, state_name),
            runtime=rt,
        )
        return

    if mode == "INTERVAL":
        on_t = int(params.get("interval_on", 300))
        off_t = int(params.get("interval_off", 900))

        cycle = on_t + off_t
        if cycle <= 0:
            apply_device_state(
                device,
                resolve_control_state(params, "off"),
                runtime=rt,
            )
            return

        phase = int(time.time()) % cycle
        state_name = (
            "interval_a"
            if phase < on_t
            else "interval_b"
        )

        apply_device_state(
            device,
            resolve_control_state(params, state_name),
            runtime=rt,
        )
        return

    if mode == "ENV":
        if device == "heating":
            control_heating_env(runtime=rt)
            return

        if device == "light":
            control_light_profile(runtime=rt)
            return

        should_run = evaluate_env_conditions(device, runtime=rt)
        set_device(device, should_run, runtime=rt)
        return


def control_light_profile(runtime=None):
    rt = resolve_runtime(runtime)
    cfg = rt.config

    now_min = minutes_now()
    day_start = int(cfg.get("DAY_START_MIN", 360))
    night_start = int(cfg.get("NIGHT_START_MIN", 1320))

    light_on = in_time_window(now_min, day_start, night_start)
    set_device("light", light_on, runtime=rt)


def control_heating_env(runtime=None):
    """Temperaturregelung im ENV-Modus mit Profil, Rampe und Hysterese."""

    rt = resolve_runtime(runtime)
    cfg = rt.config
    st = rt.state

    temp = st.live_state.get("temp")
    if temp is None:
        set_heating(False, runtime=rt)
        return

    update_temperature_setpoint(runtime=rt)

    target = st.live_state.get("temp_target")
    tol = st.live_state.get("temp_tol")

    if target is None or tol is None:
        return

    min_temp = float(cfg.get("MIN_TEMP", 18.0))
    max_temp = float(cfg.get("MAX_TEMP", 30.0))

    if temp >= max_temp:
        set_heating(False, "(MAX TEMP Schutz)", runtime=rt)
        return

    if temp <= min_temp:
        set_heating(True, "(MIN TEMP Schutz)", runtime=rt)
        return

    if temp < (target - tol):
        set_heating(True, f"(unter Soll {target:.1f}°C)", runtime=rt)
    elif temp >= target:
        set_heating(False, f"(Soll {target:.1f}°C erreicht)", runtime=rt)


def control_fan_env(runtime=None):
    rt = resolve_runtime(runtime)
    should_run = evaluate_env_conditions("fan", runtime=rt)
    set_fan(should_run, runtime=rt)


def control_ventilator_env(runtime=None):
    rt = resolve_runtime(runtime)
    cfg = rt.config
    st = rt.state

    temp = st.live_state.get("temp")
    if temp is None:
        set_vent(False, runtime=rt)
        return

    profile = get_profile(runtime=rt)

    if profile == "TAG":
        target = float(cfg.get("DAY_TEMP", 24.0))
        tol = float(cfg.get("DAY_TEMP_TOL", 1.0))
    else:
        target = float(cfg.get("NIGHT_TEMP", 20.0))
        tol = float(cfg.get("NIGHT_TEMP_TOL", 1.0))

    if temp > float(cfg.get("MAX_TEMP", 30.0)):
        set_vent(True, "(MAX TEMP Schutz)", runtime=rt)
        return

    if temp > (target + tol):
        set_vent(True, f"(Kühlung über Soll {target:.1f}°C)", runtime=rt)
    elif temp <= target:
        set_vent(False, f"(Soll {target:.1f}°C erreicht)", runtime=rt)
