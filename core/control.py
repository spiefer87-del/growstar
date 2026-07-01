#core/control.py

import time

import core.state as state

from core.config import config
from core.profile import get_profile
from core.ramp import get_ramped_target
from core.helpers import minutes_now, in_time_window
from core.actuators import (
    set_device,
    set_heating,
    set_fan,
    set_vent,
)
from core.devices import (
    get_device_mode,
    get_device_params,
)
# =========================================
# 🌡️ REGELLOGIK
# =========================================


def update_humidity_setpoint():
    profile = get_profile()

    if profile == "TAG":
        base, tol = config["DAY_HUM"], config["DAY_HUM_TOL"]
    else:
        base, tol = config["NIGHT_HUM"], config["NIGHT_HUM_TOL"]

    state.live_state["hum_target"] = base
    state.live_state["hum_tol"] = tol

def update_temperature_setpoint():
    profile = get_profile()

    if profile == "TAG":
        base = float(config["DAY_TEMP"])
        tol  = float(config["DAY_TEMP_TOL"])
    else:
        base = float(config["NIGHT_TEMP"])
        tol  = float(config["NIGHT_TEMP_TOL"])

    target = base

    if state.ramp_active:

        ramp_target = get_ramped_target()

        if ramp_target is not None:
            target = ramp_target

    # 📊 IMMER setzen – auch wenn Regelung deaktiviert
    state.live_state["temp_target"] = target
    state.live_state["temp_tol"] = tol
    print(
        f"{time.strftime('%H:%M:%S')} "
        f"({minutes_now()} min) | "
        f"profile={profile} | "
        f"ramp={state.ramp_active} | "
        f"ramp_target={state.ramp_target_temp} | "
        f"base={base:.2f} | "
        f"target={target:.2f}"
    )

def evaluate_env_conditions(device):

    cfg = config.get("DEVICE_ENV_CONFIG", {}).get(device, {})
    if not cfg:
        return False

    use_temp = cfg.get("use_temp", False)
    use_hum = cfg.get("use_hum", False)
    logic = cfg.get("logic", "OR")
    direction = cfg.get("direction", "HIGH")  # HIGH oder LOW

    results = []

    # ================= TEMP =================
    if use_temp:
        temp = state.live_state.get("temp")
        target = state.live_state.get("temp_target")
        tol = state.live_state.get("temp_tol")

        if None not in (temp, target, tol):

            if direction == "HIGH":
                results.append(temp > (target + tol))
            else:  # LOW
                results.append(temp < (target - tol))

    # ================= HUM =================
    if use_hum:
        hum = state.live_state.get("hum")
        target = state.live_state.get("hum_target")
        tol = state.live_state.get("hum_tol")

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


def control_device(device):

    mode = get_device_mode(device)
    params = get_device_params(device)

    now_min = minutes_now()

    # OFF
    if mode == "OFF":
        set_device(device, False)
        return

    # Dauerbetrieb
    if mode == "ON":
        set_device(device, True)
        return

    # Zeitgesteuert
    if mode == "TIME":
        start = int(params.get("start_min", 0))
        end   = int(params.get("end_min", 0))
        should_run = in_time_window(now_min, start, end)
        set_device(device, should_run)
        return

    # Intervall
    if mode == "INTERVAL":
        on_t  = int(params.get("interval_on", 300))
        off_t = int(params.get("interval_off", 900))

        cycle = on_t + off_t
        phase = int(time.time()) % cycle

        set_device(device, phase < on_t)
        return

    # Umgebung
    if mode == "ENV":
        if device == "heating":
            control_heating_env()
            return
        
        if device == "light":
            control_light_profile()
            return
        
        should_run = evaluate_env_conditions(device)
        set_device(device, should_run)
        return
    
def control_light_profile():
    now_min = minutes_now()

    day_start = int(config.get("DAY_START_MIN", 360))
    night_start = int(config.get("NIGHT_START_MIN", 1320))

    # Licht an = Tageszeit
    light_on = in_time_window(now_min, day_start, night_start)

    set_device("light", light_on)


def control_heating_env():
    """
    Temperaturregelung im ENV Modus.
    Nutzt Profil + Rampen + Hysterese.
    """

    temp = state.live_state.get("temp")
    if temp is None:
        set_heating(False)
        return

    update_temperature_setpoint()

    target = state.live_state.get("temp_target")
    tol    = state.live_state.get("temp_tol")

    if target is None or tol is None:
        return

    min_temp = float(config.get("MIN_TEMP", 18.0))
    max_temp = float(config.get("MAX_TEMP", 30.0))

    # 🔴 Absolute Sicherheitsgrenzen
    if temp >= max_temp:
        set_heating(False, "(MAX TEMP Schutz)")
        return

    if temp <= min_temp:
        set_heating(True, "(MIN TEMP Schutz)")
        return

    # 🟢 Normale Hysterese-Regelung
    # Einschalten unter Soll - Toleranz
    if temp < (target - tol):
        set_heating(True, f"(unter Soll {target:.1f}°C)")

    # Ausschalten erst wenn Soll erreicht
    elif temp >= target:
        set_heating(False, f"(Soll {target:.1f}°C erreicht)")

    #print("HEATING ENV CHECK:",
      #"Temp:", temp,
      #"Target:", target,
      #"Tol:", tol,
      #"Mode:", get_device_mode("heating"))


def control_fan_env():
    should_run = evaluate_env_conditions("fan")
    set_fan(should_run)



def control_ventilator_env():
    """
    Umgebungskühlung:
    Ventilator läuft, wenn Temperatur über Soll + Toleranz.
    Sollwerte kommen aus aktivem Profil.
    """

    temp = state.live_state.get("temp")
    if temp is None:
        set_vent(False)
        return

    # Aktuelle Zielwerte holen
    profile = get_profile()

    if profile == "TAG":
        target = float(config.get("DAY_TEMP", 24.0))
        tol    = float(config.get("DAY_TEMP_TOL", 1.0))
    else:
        target = float(config.get("NIGHT_TEMP", 20.0))
        tol    = float(config.get("NIGHT_TEMP_TOL", 1.0))

    # Sicherheitsgrenze
    if temp > config.get("MAX_TEMP", 30.0):
        set_vent(True, "(MAX TEMP Schutz)")
        return

    # Regelung
    if temp > (target + tol):
        set_vent(True, f"(Kühlung über Soll {target:.1f}°C)")
    elif temp <= target:
        set_vent(False, f"(Soll {target:.1f}°C erreicht)")

