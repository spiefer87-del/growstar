# core/control.py

import time

from core.runtime import resolve_runtime
from core.profile import get_profile
from core.ramp import get_ramped_target
from core.light_sun import calculate_light_sun_state
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
from core.vpd_control import apply_vpd_device_plan, vpd_manages_device


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
    # Unveränderter Sollwert der klassischen Profilregelung. VPD-AUTO darf
    # den sichtbaren Live-Sollwert später im selben Zyklus durch das gekoppelte
    # Temperatur-/Feuchteziel ersetzen. Für Fallback und Reset bleibt das
    # klassische Original dadurch jederzeit eindeutig verfügbar.
    st.live_state["climate_hum_target"] = base
    st.live_state["climate_hum_tol"] = tol
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
    # Unveränderter Sollwert der klassischen Profil-/Rampenlogik. Ein
    # übergeordneter VPD-Koordinator darf temp_target später im selben Zyklus
    # anpassen, ohne dadurch im nächsten Zyklus seine eigene Korrektur als
    # neue Profilbasis zu missverstehen.
    st.live_state["climate_temp_target"] = target
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

        state_name = "time" if should_run else "off"
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
        # Die VPD-Zustandsmaschine übernimmt ausschließlich explizite
        # ENV-Geräte und wendet ihren Plan weiterhin über apply_device_state an.
        # OFF/ON/TIME/INTERVAL bleiben jederzeit autoritativ beim Benutzer.
        if vpd_manages_device(device, runtime=rt):
            apply_vpd_device_plan(device, runtime=rt)
            return

        if device == "heating":
            control_heating_env(runtime=rt)
            return

        if device == "light":
            control_light_profile(runtime=rt)
            return

        if device == "fan":
            control_fan_env(runtime=rt)
            return

        should_run = evaluate_env_conditions(device, runtime=rt)
        state_name = "env" if should_run else "off"
        apply_device_state(
            device,
            resolve_control_state(params, state_name),
            runtime=rt,
        )
        return


def control_light_profile(runtime=None):
    """Profillicht mit optionalem Sonnenaufgang/Sonnenuntergang."""

    rt = resolve_runtime(runtime)
    cfg = rt.config
    st = rt.state

    now_min = minutes_now()
    day_start = int(cfg.get("DAY_START_MIN", 360))
    night_start = int(cfg.get("NIGHT_START_MIN", 1320))

    light_on = in_time_window(now_min, day_start, night_start)
    params = get_device_params("light", runtime=rt)

    if not light_on:
        with rt.state_lock:
            st.live_state["light_sun_active"] = False
            st.live_state["light_sun_phase"] = "night"
            st.live_state["light_sun_level"] = None
            st.live_state["light_sun_progress"] = 0.0
        apply_device_state(
            "light",
            resolve_control_state(params, "off"),
            runtime=rt,
        )
        return

    env_state = resolve_control_state(params, "env")

    from core.capability_routing import controller_assignment_for_config
    light_controller_assignment = controller_assignment_for_config(
        cfg,
        "light",
    )

    if (
        cfg.get("LIGHT_SUN_ENABLED", 0)
        and not isinstance(light_controller_assignment, dict)
    ):
        with rt.state_lock:
            st.live_state["light_sun_active"] = False
            st.live_state["light_sun_phase"] = "controller_required"
            st.live_state["light_sun_level"] = None
            st.live_state["light_sun_progress"] = 0.0

        apply_device_state("light", env_state, runtime=rt)
        return

    if not cfg.get("LIGHT_SUN_ENABLED", 0):
        with rt.state_lock:
            st.live_state["light_sun_active"] = False
            st.live_state["light_sun_phase"] = "disabled"
            st.live_state["light_sun_level"] = None
            st.live_state["light_sun_progress"] = 0.0
        apply_device_state("light", env_state, runtime=rt)
        return

    controller = dict(env_state.get("controller") or {})
    target_level = controller.get("level")

    # Kein gespeicherter dimmbarer ENV-Level: altes EIN/AUS-Verhalten behalten.
    if target_level is None:
        with rt.state_lock:
            st.live_state["light_sun_active"] = False
            st.live_state["light_sun_phase"] = "no_level_controller"
            st.live_state["light_sun_level"] = None
            st.live_state["light_sun_progress"] = 0.0
        apply_device_state("light", env_state, runtime=rt)
        return

    sun = calculate_light_sun_state(
        now_min=now_min,
        day_start=day_start,
        night_start=night_start,
        sunrise_duration=cfg.get("LIGHT_SUNRISE_DURATION_MIN", 30),
        sunset_duration=cfg.get("LIGHT_SUNSET_DURATION_MIN", 30),
        min_level=cfg.get("LIGHT_SUN_MIN_LEVEL", 11),
        target_level=target_level,
    )

    if not sun["on"]:
        apply_device_state(
            "light",
            resolve_control_state(params, "off"),
            runtime=rt,
        )
        return

    controller["level"] = int(sun["level"])
    env_state = dict(env_state)
    env_state["controller"] = controller

    with rt.state_lock:
        st.live_state["light_sun_active"] = True
        st.live_state["light_sun_phase"] = sun["phase"]
        st.live_state["light_sun_level"] = int(sun["level"])
        st.live_state["light_sun_progress"] = sun["progress"]

    apply_device_state("light", env_state, runtime=rt)


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


def _env_inputs_ready(device, runtime=None):
    """Prüft, ob alle für ENV ausgewählten Sensorwerte verwertbar sind.

    Für die Standby-Entscheidung bedeutet "kein Regelbedarf" nicht automatisch
    "alles okay". Fehlt ein ausgewählter Messwert oder sein Sollwert/Toleranz,
    wird Standby bewusst nicht freigegeben.
    """

    rt = resolve_runtime(runtime)
    cfg = rt.config
    st = rt.state

    env_cfg = cfg.get("DEVICE_ENV_CONFIG", {}).get(device, {})
    if not isinstance(env_cfg, dict):
        return False

    selected = 0

    if env_cfg.get("use_temp", False):
        selected += 1
        if None in (
            st.live_state.get("temp"),
            st.live_state.get("temp_target"),
            st.live_state.get("temp_tol"),
        ):
            return False

    if env_cfg.get("use_hum", False):
        selected += 1
        if None in (
            st.live_state.get("hum"),
            st.live_state.get("hum_target"),
            st.live_state.get("hum_tol"),
        ):
            return False

    return selected > 0


def control_fan_env(runtime=None):
    """ENV-Lüfterregelung mit optionaler Standby-Grundlüftung.

    Regelbedarf:
        normale ENV-Leistung.

    Alle ausgewählten Werte innerhalb der Grenzen:
        optionaler env_standby-Zustand.

    Standby deaktiviert, nicht vollständig konfiguriert oder Sensorstatus
    unvollständig:
        historisches/sicheres AUS-Verhalten.
    """

    rt = resolve_runtime(runtime)
    cfg = rt.config
    st = rt.state

    params = get_device_params("fan", runtime=rt)
    env_cfg = cfg.get("DEVICE_ENV_CONFIG", {}).get("fan", {})
    if not isinstance(env_cfg, dict):
        env_cfg = {}

    should_run = evaluate_env_conditions("fan", runtime=rt)

    if should_run:
        state_name = "env"
        phase = "regulation"

    elif not _env_inputs_ready("fan", runtime=rt):
        state_name = "off"
        phase = "sensor_unavailable"

    elif env_cfg.get("standby_enabled", False):
        standby_state = resolve_control_state(
            params,
            "env_standby",
        )

        # Grundlüftung ist nur sinnvoll, wenn wirklich ein separater
        # Controller-Sollwert vorhanden ist. Shelly EIN ohne Controller-Level
        # könnte bei manchen Lüftern sonst Vollleistung bedeuten.
        if (
            standby_state.get("power")
            and standby_state.get("controller")
        ):
            state_name = "env_standby"
            phase = "standby"
        else:
            state_name = "off"
            phase = "standby_unavailable"

    else:
        state_name = "off"
        phase = "off"

    with rt.state_lock:
        st.live_state["fan_env_phase"] = phase

    apply_device_state(
        "fan",
        resolve_control_state(params, state_name),
        runtime=rt,
    )


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
