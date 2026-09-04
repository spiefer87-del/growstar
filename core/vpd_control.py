"""Intelligente, stationsbezogene VPD-Regelung.

Die VPD-Regelung ist ein Koordinator oberhalb der bestehenden ENV-Gerätepfade.
Sie umgeht weder Shelly-Power, Controller-Validierung, Shadow-Gates noch den
Safety-Supervisor. Nur Geräte, die ausdrücklich im Modus ``ENV`` stehen,
können im AUTO-Modus übernommen werden.

Regelstrategie bei zu niedrigem VPD / zu hoher Feuchte:

1. Abluft nur einsetzen, wenn die Außenluft tatsächlich trockener ist.
2. Wirkung über ein konfigurierbares Zeitfenster beobachten.
3. Ohne ausreichende Wirkung den Temperatur-Sollwert schrittweise anheben.
4. Erst wenn auch das nicht genügt, den Entfeuchter anfordern.

Bei zu hohem VPD wird dagegen zuerst das Temperaturziel innerhalb des
phasenbezogenen Min-/Max-Fensters abgesenkt. Geeignete kühlere Außenluft darf
diesen Schritt unterstützen; erst danach folgen Befeuchtungsschritte.

Eine aktivierte Profilrampe interpoliert im intelligenten Modus VPD-Ziel,
Toleranz und Klimafenster. Klassische DAY_TEMP/NIGHT_TEMP-Werte sind keine
Regelbasis des VPD-Koordinators mehr.

Der MONITOR-Modus berechnet exakt denselben Plan, übernimmt aber keine Aktoren.
"""

from __future__ import annotations

from copy import deepcopy
import math
from statistics import median
import time

from core.controller_states import apply_device_state, resolve_control_state
from core.devices import get_device_env_config, get_device_mode, get_device_params
from core.helpers import calculate_vpd
from core.runtime import resolve_runtime
from core.vpd import (
    VPD_CONTROL_MODES,
    VPD_ENGINE_KEY as _ENGINE_KEY,
    VPD_GENERATION_KEY as _GENERATION_KEY,
    VPD_MANAGED_DEVICES,
    VPD_PUBLIC_KEY as _PUBLIC_KEY,
    calculate_vpd_schedule,
    reset_vpd_control,
    validate_vpd_environment_alignment,
)


def _saturation_vapor_pressure(temp_c):
    return 0.6108 * math.exp((17.27 * float(temp_c)) / (float(temp_c) + 237.3))


def _actual_vapor_pressure(temp_c, humidity):
    return _saturation_vapor_pressure(temp_c) * (float(humidity) / 100.0)


def _absolute_humidity(temp_c, humidity):
    # Wasserdampf in g/m³; vapor pressure wird von kPa nach hPa umgerechnet.
    vapor_hpa = _actual_vapor_pressure(temp_c, humidity) * 10.0
    return 216.7 * vapor_hpa / (float(temp_c) + 273.15)


def _clip(value, minimum, maximum):
    return max(float(minimum), min(float(maximum), float(value)))


def _device_is_env(runtime, device):
    try:
        return get_device_mode(device, runtime=runtime) == "ENV"
    except (TypeError, ValueError):
        return False


def _current_power(runtime, device):
    if not runtime.control_enabled:
        desired = runtime.shadow_outputs.get(device)
        if isinstance(desired, bool):
            return desired
    return bool(getattr(runtime.state, f"{device}_on", False))


def _off_action(runtime, device, reason):
    params = get_device_params(device, runtime=runtime)
    state = resolve_control_state(params, "off")
    return {**state, "reason": reason}


def _on_action(runtime, device, reason):
    params = get_device_params(device, runtime=runtime)
    state = resolve_control_state(params, "env")
    return {**state, "reason": reason}


def _fan_limits(runtime):
    params = get_device_params("fan", runtime=runtime)
    env_state = resolve_control_state(params, "env")
    standby_state = resolve_control_state(params, "env_standby")

    env_controller = dict(env_state.get("controller") or {})
    standby_controller = dict(standby_state.get("controller") or {})

    env_level = env_controller.get("level")
    standby_level = standby_controller.get("level") if standby_state.get("power") else None

    try:
        env_level = int(env_level) if env_level is not None else None
    except (TypeError, ValueError):
        env_level = None
    try:
        standby_level = int(standby_level) if standby_level is not None else None
    except (TypeError, ValueError):
        standby_level = None

    if env_level is None:
        minimum = maximum = None
    elif standby_level is None:
        minimum = maximum = env_level
    else:
        minimum = min(standby_level, env_level)
        maximum = max(standby_level, env_level)

    return {
        "env_state": env_state,
        "standby_state": standby_state,
        "minimum": minimum,
        "maximum": maximum,
    }


def _fan_idle_action(runtime):
    params = get_device_params("fan", runtime=runtime)
    env = get_device_env_config("fan", runtime=runtime)
    standby = resolve_control_state(params, "env_standby")

    if (
        bool(env.get("standby_enabled"))
        and bool(standby.get("power"))
        and bool(standby.get("controller"))
    ):
        return {**standby, "reason": "(VPD Grundlüftung)"}
    return {**resolve_control_state(params, "off"), "reason": "(VPD kein Abluftbedarf)"}


def _fan_regulation_action(runtime, level, reason):
    limits = _fan_limits(runtime)
    state = deepcopy(limits["env_state"])
    controller = dict(state.get("controller") or {})
    if level is not None and "level" in controller:
        controller["level"] = int(level)
    state["controller"] = controller
    return {**state, "reason": reason}


def _next_fan_level(current, minimum, maximum, step_percent):
    if current is None or minimum is None or maximum is None:
        return current
    if current >= maximum:
        return maximum

    span = max(0, int(maximum) - int(minimum))
    increment = max(1, int(math.ceil(span * float(step_percent) / 100.0)))
    return min(int(maximum), int(current) + increment)


def _thermostat_action(runtime, *, temp, target, tolerance, temp_min, temp_max, reason):
    current = _current_power(runtime, "heating")

    if temp >= temp_max:
        enabled = False
    elif temp <= temp_min:
        enabled = True
    elif temp < target - tolerance:
        enabled = True
    elif temp >= target:
        enabled = False
    else:
        enabled = current

    if enabled:
        return _on_action(runtime, "heating", reason)
    return _off_action(runtime, "heating", reason)


def _stage_effect(engine, direction):
    samples = list(engine.get("samples") or [])
    if not samples:
        return 0.0

    first_ts = samples[0][0]
    last_ts = samples[-1][0]
    early = [value for ts, value in samples if ts <= first_ts + 60.0]
    recent = [value for ts, value in samples if ts >= last_ts - 60.0]
    if not early or not recent:
        return 0.0

    if direction == "raise":
        return float(median(recent) - median(early))
    return float(median(early) - median(recent))


def _set_stage(engine, *, direction, stage, now, vpd, note=None):
    engine["direction"] = direction
    engine["stage"] = stage
    engine["stage_started_at"] = float(now)
    engine["samples"] = [(float(now), float(vpd))]
    engine["last_transition_note"] = note


def _append_sample(engine, now, vpd, effect_window_sec):
    samples = engine.setdefault("samples", [])
    samples.append((float(now), float(vpd)))
    cutoff = float(now) - max(900.0, float(effect_window_sec) * 2.0)
    engine["samples"] = [item for item in samples if item[0] >= cutoff][-900:]


def _assignment_source_ids(cfg):
    assignments = cfg.get("SENSOR_ASSIGNMENTS") or {}
    if not isinstance(assignments, dict):
        return set(), set()

    indoor = {
        str((assignments.get(name) or {}).get("source_id") or "").strip()
        for name in ("temperature", "humidity")
    }
    outside = {
        str((assignments.get(name) or {}).get("source_id") or "").strip()
        for name in ("outside_temperature", "outside_humidity")
    }
    return {item for item in indoor if item}, {item for item in outside if item}


def _readiness(runtime, values):
    st = runtime.state
    blockers = []

    if values["temp"] is None or bool(getattr(st, "temp_stale", False)):
        blockers.append("Temperatursensor innen nicht verfügbar")
    if values["hum"] is None or bool(getattr(st, "hum_stale", False)):
        blockers.append("Feuchtesensor innen nicht verfügbar")
    if values["outside_temp"] is None:
        blockers.append("Außentemperatur nicht verfügbar")
    if values["outside_hum"] is None:
        blockers.append("Außenfeuchte nicht verfügbar")

    plausible_ranges = {
        "temp": (-50.0, 80.0, "Temperatur innen"),
        "hum": (0.0, 100.0, "Feuchte innen"),
        "outside_temp": (-50.0, 80.0, "Außentemperatur"),
        "outside_hum": (0.0, 100.0, "Außenfeuchte"),
    }
    for key, (minimum, maximum, label) in plausible_ranges.items():
        value = values.get(key)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            blockers.append(f"{label} ist nicht numerisch")
            continue
        if not math.isfinite(number) or number < minimum or number > maximum:
            blockers.append(f"{label} ist unplausibel")

    indoor_ids, outside_ids = _assignment_source_ids(runtime.config)
    if not outside_ids:
        blockers.append("Außensensor ist nicht zugewiesen")
    elif indoor_ids.intersection(outside_ids):
        blockers.append("Innen- und Außensensor dürfen nicht dieselbe Quelle sein")

    return blockers


def _base_temp_target(runtime, settings, current_temp=None):
    """Temperaturreferenz des VPD-Reglers ohne klassische Sollwertkopplung."""

    st = runtime.state
    live = st.live_state

    # Der letzte eigene VPD-Sollwert gewinnt. Beim ersten Zyklus wird die
    # gemessene Temperatur stoßfrei übernommen. DAY_TEMP/NIGHT_TEMP dienen im
    # AUTO-Modus damit nicht länger als Rampenbasis, bleiben aber außerhalb
    # einer bereiten AUTO-Übernahme als klassischer Fallback erhalten.
    candidates = (
        live.get("vpd_temp_target"),
        current_temp,
        live.get("temp"),
        live.get("climate_temp_target"),
    )
    for candidate in candidates:
        try:
            number = float(candidate)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            return _clip(number, settings["temp_min"], settings["temp_max"])

    return (float(settings["temp_min"]) + float(settings["temp_max"])) / 2.0


def _temperature_for_vpd(target_vpd, humidity, temp_min, temp_max):
    """Temperatur, die beim aktuellen RH rechnerisch den Ziel-VPD ergibt."""

    humidity = _clip(humidity, 0.0, 99.9)
    vapor_fraction = 1.0 - humidity / 100.0
    if vapor_fraction <= 0.0:
        return float(temp_max)

    saturation_target = float(target_vpd) / vapor_fraction
    if saturation_target <= 0.0:
        return float(temp_min)

    logarithm = math.log(saturation_target / 0.6108)
    denominator = 17.27 - logarithm
    if abs(denominator) < 1e-9:
        return float(temp_max)

    temperature = 237.3 * logarithm / denominator
    return _clip(temperature, temp_min, temp_max)


def _step_temperature(current, destination, step):
    current = float(current)
    destination = float(destination)
    step = abs(float(step))
    if destination < current:
        return max(destination, current - step)
    if destination > current:
        return min(destination, current + step)
    return current


def _settings_for_schedule(runtime, settings):
    profile = str(
        runtime.state.live_state.get("profile")
        or runtime.state.current_profile
        or "TAG"
    ).upper()
    profile = "NACHT" if profile == "NACHT" else "TAG"
    phase, ramp = calculate_vpd_schedule(settings, runtime.config, profile)
    active = dict(settings)
    active.update(phase)
    return active, profile, ramp


def _public_waiting_state(settings, profile, values, blockers, ramp):
    return {
        "mode": settings["mode"],
        "active": False,
        "takeover": False,
        "ready": False,
        "fallback": settings["mode"] == "AUTO",
        "stage": "waiting_sensors",
        "stage_label": "Warte auf Sensoren",
        "direction": None,
        "reason": "; ".join(blockers),
        "next_step_label": "Sensorbasis vervollständigen; danach plant AUTO neu",
        "vpd": values.get("vpd"),
        "profile": profile,
        "target": settings["target"],
        "tolerance": settings["tolerance"],
        "ramp": ramp,
        "range": {
            "temp_min": settings["temp_min"],
            "temp_max": settings["temp_max"],
            "hum_min": settings["hum_min"],
            "hum_max": settings["hum_max"],
        },
        "managed_devices": [],
        "actions": {},
        "blockers": list(blockers),
    }


def _next_step_label(
    engine,
    *,
    settings,
    availability,
    outside_humidifying,
):
    """Beschreibt ausschließlich den im Zustandsautomaten möglichen Folgeschritt."""

    direction = engine.get("direction")
    stage = engine.get("stage") or "in_band"

    if direction is None or stage == "in_band":
        return "Zielband halten und Klima weiter beobachten"
    if stage == "limited":
        return "Auf eine Klimaänderung oder eine weitere ENV-Aktorstufe warten"

    if direction == "raise":
        if stage == "exhaust":
            if (
                availability["heating"]
                and float(engine.get("temp_target") or settings["temp_min"])
                < settings["temp_max"]
            ):
                return "Bei zu geringer Abluftwirkung die Temperatur leicht anheben"
            if availability["dehumidifier"]:
                return "Bei zu geringer Abluftwirkung den Entfeuchter zuschalten"
            return "Abluftwirkung erneut bewerten und die sichere Stufe halten"
        if stage == "heat":
            if availability["dehumidifier"]:
                return "Temperaturwirkung prüfen; bei Bedarf den Entfeuchter zuschalten"
            return "Temperaturwirkung prüfen und den Sollwert gegebenenfalls nachführen"
        if stage == "dehumidify":
            return "Entfeuchterwirkung bis zum VPD-Zielband weiter prüfen"

    if direction == "lower":
        if stage in {"cool", "conserve"}:
            if availability["humidifier"]:
                return "Kühlwirkung prüfen; bei Bedarf den Luftbefeuchter zuschalten"
            if availability["fan"] and outside_humidifying:
                return "Kühlwirkung prüfen; bei Bedarf feuchtere Außenluft nutzen"
            return "Temperaturwirkung erneut bewerten und die sichere Stufe halten"
        if stage == "humidify" and availability["fan"] and outside_humidifying:
            return "Befeuchterwirkung prüfen; bei Bedarf Außenluft ergänzen"
        if stage in {"humidify", "humidify_outside", "outside_assist"}:
            return "VPD-Senkung weiter prüfen und bis zum Zielband nachführen"

    return "Wirkung der aktuellen Strategie prüfen und anschließend neu planen"


def _advance_raise_stage(
    runtime,
    engine,
    *,
    now,
    vpd,
    improvement,
    settings,
    availability,
):
    stage = engine.get("stage")
    min_effect = settings["min_effect"]

    if stage == "exhaust":
        if improvement >= min_effect:
            current = engine.get("fan_level")
            minimum = engine.get("fan_min")
            maximum = engine.get("fan_max")
            if current is not None and maximum is not None and current < maximum:
                engine["fan_level"] = _next_fan_level(
                    current,
                    minimum,
                    maximum,
                    settings["fan_step"],
                )
                note = "Abluft wirkt; Leistung wurde behutsam erhöht"
            else:
                note = "Abluft wirkt; Wirkung wird weiter beobachtet"
            _set_stage(engine, direction="raise", stage="exhaust", now=now, vpd=vpd, note=note)
            return

        if availability["heating"] and engine.get("temp_target", 0) < settings["temp_max"]:
            engine["temp_target"] = min(
                settings["temp_max"],
                float(engine.get("temp_target") or settings["temp_min"])
                + settings["temp_step"],
            )
            _set_stage(
                engine,
                direction="raise",
                stage="heat",
                now=now,
                vpd=vpd,
                note="Abluft ohne ausreichende Wirkung; Temperatur leicht angehoben",
            )
        elif availability["dehumidifier"]:
            _set_stage(
                engine,
                direction="raise",
                stage="dehumidify",
                now=now,
                vpd=vpd,
                note="Abluft ohne Wirkung und keine Temperaturreserve; Entfeuchter angefordert",
            )
        else:
            _set_stage(engine, direction="raise", stage="limited", now=now, vpd=vpd, note="Keine weitere sichere VPD-Stufe verfügbar")
        return

    if stage == "heat":
        current_target = float(engine.get("temp_target") or settings["temp_min"])
        if improvement >= min_effect and current_target < settings["temp_max"]:
            engine["temp_target"] = min(
                settings["temp_max"],
                current_target + settings["temp_step"],
            )
            _set_stage(engine, direction="raise", stage="heat", now=now, vpd=vpd, note="Temperaturanhebung wirkt; Sollwert vorsichtig weiter angehoben")
        elif improvement >= min_effect:
            _set_stage(engine, direction="raise", stage="heat", now=now, vpd=vpd, note="Temperaturanhebung wirkt; Maximalwert bleibt bestehen")
        elif availability["dehumidifier"]:
            _set_stage(engine, direction="raise", stage="dehumidify", now=now, vpd=vpd, note="Temperaturanhebung ohne ausreichende Wirkung; Entfeuchter angefordert")
        else:
            _set_stage(engine, direction="raise", stage="limited", now=now, vpd=vpd, note="Temperatur ohne Wirkung; kein Entfeuchter im ENV-Modus")
        return

    if stage == "dehumidify":
        # Die letzte Stufe bleibt aktiv, bis das Zielband erreicht ist. Das
        # eigentliche Abschalten erfolgt dann sofort über den in-band-Pfad.
        _set_stage(engine, direction="raise", stage="dehumidify", now=now, vpd=vpd, note="Entfeuchterwirkung wird weiter beobachtet")


def _advance_lower_stage(
    engine,
    *,
    now,
    vpd,
    improvement,
    settings,
    availability,
    outside_humidifying,
    preferred_temp,
):
    stage = engine.get("stage")

    if stage in {"cool", "conserve"}:
        if improvement >= settings["min_effect"]:
            current_target = float(
                engine.get("temp_target") or settings["temp_min"]
            )
            engine["temp_target"] = _clip(
                _step_temperature(
                    current_target,
                    min(float(preferred_temp), current_target),
                    settings["temp_step"],
                ),
                settings["temp_min"],
                settings["temp_max"],
            )
            _set_stage(
                engine,
                direction="lower",
                stage="cool",
                now=now,
                vpd=vpd,
                note="Temperaturabsenkung wirkt; Sollwert folgt dem VPD-Ziel",
            )
        elif availability["humidifier"]:
            _set_stage(engine, direction="lower", stage="humidify", now=now, vpd=vpd, note="Temperaturabsenkung ohne ausreichende Wirkung; Luftbefeuchter angefordert")
        elif availability["fan"] and outside_humidifying:
            _set_stage(engine, direction="lower", stage="outside_assist", now=now, vpd=vpd, note="Temperaturabsenkung ohne ausreichende Wirkung; feuchtere Außenluft unterstützt")
        else:
            _set_stage(engine, direction="lower", stage="limited", now=now, vpd=vpd, note="Keine weitere sichere VPD-Stufe verfügbar")
        return

    if stage == "humidify" and improvement < settings["min_effect"] and availability["fan"] and outside_humidifying:
        _set_stage(engine, direction="lower", stage="humidify_outside", now=now, vpd=vpd, note="Luftbefeuchter ohne ausreichende Wirkung; feuchtere Außenluft unterstützt")
    elif stage in {"humidify", "humidify_outside", "outside_assist"}:
        _set_stage(engine, direction="lower", stage=stage, now=now, vpd=vpd, note="VPD-Senkung wird weiter beobachtet")


def update_vpd_control(runtime=None, *, now=None):
    """Berechnet den nächsten VPD-Plan und veröffentlicht seine Telemetrie."""

    rt = resolve_runtime(runtime)
    st = rt.state
    cfg = rt.config
    now = time.time() if now is None else float(now)

    try:
        settings = validate_vpd_environment_alignment(cfg)
    except (TypeError, ValueError) as exc:
        public = {
            "mode": str(cfg.get("VPD_CONTROL_MODE", "OFF") or "OFF").upper(),
            "active": False,
            "takeover": False,
            "ready": False,
            "fallback": True,
            "stage": "invalid_config",
            "stage_label": "Konfiguration fehlerhaft",
            "reason": str(exc),
            "managed_devices": [],
            "actions": {},
        }
        with rt.state_lock:
            st.live_state[_PUBLIC_KEY] = public
            st.live_state.pop(_ENGINE_KEY, None)
        return public

    if settings["mode"] == "OFF":
        public = {
            "mode": "OFF",
            "active": False,
            "takeover": False,
            "ready": False,
            "fallback": False,
            "stage": "disabled",
            "stage_label": "Aus",
            "reason": "Intelligente VPD-Steuerung ist deaktiviert",
            "managed_devices": [],
            "actions": {},
        }
        with rt.state_lock:
            st.live_state[_PUBLIC_KEY] = public
            st.live_state.pop(_ENGINE_KEY, None)
            st.live_state.pop("vpd_temp_target", None)
            st.live_state.pop("vpd_base_temp_target", None)
        return public

    try:
        settings, profile, ramp = _settings_for_schedule(rt, settings)
    except ValueError as exc:
        public = {
            "mode": settings["mode"],
            "active": False,
            "takeover": False,
            "ready": False,
            "fallback": True,
            "stage": "invalid_config",
            "stage_label": "Konfiguration fehlerhaft",
            "reason": str(exc),
            "managed_devices": [],
            "actions": {},
        }
        with rt.state_lock:
            st.live_state[_PUBLIC_KEY] = public
            st.live_state.pop(_ENGINE_KEY, None)
        return public

    with rt.state_lock:
        values = {
            "temp": st.live_state.get("temp"),
            "hum": st.live_state.get("hum"),
            "vpd": st.live_state.get("vpd"),
            "outside_temp": st.live_state.get("outside_temp"),
            "outside_hum": st.live_state.get("outside_hum"),
        }
        generation = st.live_state.get(_GENERATION_KEY, 0)

    blockers = _readiness(rt, values)
    if blockers:
        public = _public_waiting_state(
            settings,
            profile,
            values,
            blockers,
            ramp,
        )
        with rt.state_lock:
            st.live_state[_PUBLIC_KEY] = public
            st.live_state.pop(_ENGINE_KEY, None)
            st.live_state.pop("vpd_temp_target", None)
            st.live_state.pop("vpd_base_temp_target", None)
        return public

    temp = float(values["temp"])
    hum = float(values["hum"])
    outside_temp = float(values["outside_temp"])
    outside_hum = float(values["outside_hum"])
    vpd = float(calculate_vpd(temp, hum))
    target = settings["target"]
    error = vpd - target

    inside_ah = _absolute_humidity(temp, hum)
    outside_ah = _absolute_humidity(outside_temp, outside_hum)
    inside_vapor = _actual_vapor_pressure(temp, hum)
    outside_vapor = _actual_vapor_pressure(outside_temp, outside_hum)
    outside_drying = outside_ah <= inside_ah - 0.3
    outside_humidifying = outside_vapor >= inside_vapor + 0.05
    outside_cooling = outside_temp <= temp - 0.5
    outside_vpd = float(calculate_vpd(outside_temp, outside_hum))
    # Reine Außen-VPD-Werte überschätzen sehr kalte, aber extrem trockene Luft.
    # Für die Kühlhilfe wird deshalb ein konservativer Mischzustand aus halber
    # Temperaturannäherung und dem Außen-Dampfdruck bewertet.
    projected_exchange_temp = (temp + outside_temp) / 2.0
    projected_exchange_vpd = max(
        0.0,
        _saturation_vapor_pressure(projected_exchange_temp) - outside_vapor,
    )
    outside_lowering = (
        outside_cooling
        and projected_exchange_vpd < vpd - 0.02
    )

    availability = {
        device: _device_is_env(rt, device)
        for device in VPD_MANAGED_DEVICES
    }
    managed_devices = [device for device, available in availability.items() if available]

    base_target = _base_temp_target(rt, settings, current_temp=temp)
    preferred_temp = _temperature_for_vpd(
        target,
        hum,
        settings["temp_min"],
        settings["temp_max"],
    )

    with rt.state_lock:
        engine = deepcopy(st.live_state.get(_ENGINE_KEY))
        if not isinstance(engine, dict):
            engine = {}

    # Beginn/Ende einer VPD-Rampe und der reale Tag-/Nachtwechsel eröffnen ein
    # neues Zielband. Keine Wirkungsprobe oder Eskalationsstufe darf aus dem
    # vorherigen Zeitabschnitt übernommen werden.
    if engine.get("schedule_key") != ramp["key"]:
        engine = {}
    engine["profile"] = profile
    engine["schedule_key"] = ramp["key"]

    engine.setdefault("temp_target", base_target)
    engine["base_temp_target"] = base_target
    engine["temp_target"] = _clip(
        engine.get("temp_target", base_target),
        settings["temp_min"],
        settings["temp_max"],
    )

    fan_limits = _fan_limits(rt)
    engine["fan_min"] = fan_limits["minimum"]
    engine["fan_max"] = fan_limits["maximum"]
    if engine.get("fan_level") is None:
        engine["fan_level"] = fan_limits["minimum"]

    low_needed = vpd < target - settings["tolerance"]
    high_needed = vpd > target + settings["tolerance"]
    temp_low = temp < settings["temp_min"]
    temp_high = temp > settings["temp_max"]

    # Das erlaubte Feuchtefenster ist eine harte Betriebsgrenze. Außerhalb
    # dieses Fensters hat seine Rückführung Vorrang vor dem Komfort-Zielwert;
    # innerhalb entscheidet wieder ausschließlich das VPD-Zielband.
    if hum > settings["hum_max"]:
        low_needed, high_needed = True, False
    elif hum < settings["hum_min"]:
        low_needed, high_needed = False, True

    direction = "raise" if low_needed else "lower" if high_needed else None

    if direction != engine.get("direction"):
        engine["temp_target"] = base_target
        engine["fan_level"] = fan_limits["minimum"]

        if direction == "raise":
            if availability["fan"] and outside_drying:
                initial_stage = "exhaust"
            elif availability["heating"] and temp < settings["temp_max"]:
                initial_stage = "heat"
                engine["temp_target"] = min(
                    settings["temp_max"],
                    max(base_target, temp) + settings["temp_step"],
                )
            elif availability["dehumidifier"]:
                initial_stage = "dehumidify"
            else:
                initial_stage = "limited"
            _set_stage(engine, direction="raise", stage=initial_stage, now=now, vpd=vpd, note="VPD ist zu niedrig")
        elif direction == "lower":
            temperature_path_available = bool(
                availability["heating"]
                or (availability["fan"] and outside_lowering)
            )
            if (
                temperature_path_available
                and preferred_temp < base_target - 0.01
            ):
                engine["temp_target"] = _step_temperature(
                    base_target,
                    preferred_temp,
                    settings["temp_step"],
                )
                initial_stage = "cool"
                note = "VPD ist zu hoch; Temperatur wird bevorzugt abgesenkt"
            elif availability["humidifier"]:
                initial_stage = "humidify"
                note = "Temperaturgrenze erreicht; Luftbefeuchter angefordert"
            elif availability["fan"] and outside_humidifying:
                initial_stage = "outside_assist"
                note = "Temperaturgrenze erreicht; feuchtere Außenluft unterstützt"
            else:
                initial_stage = "limited"
                note = "Keine sichere Stufe zur VPD-Senkung verfügbar"
            _set_stage(
                engine,
                direction="lower",
                stage=initial_stage,
                now=now,
                vpd=vpd,
                note=note,
            )
        else:
            _set_stage(engine, direction=None, stage="in_band", now=now, vpd=vpd, note="VPD und Betriebsfenster sind im Ziel")
    else:
        _append_sample(engine, now, vpd, settings["effect_window_sec"])

    if direction is None:
        engine["temp_target"] = base_target

    elapsed = max(0.0, now - float(engine.get("stage_started_at") or now))
    improvement = _stage_effect(engine, direction) if direction else 0.0

    if direction and elapsed >= settings["effect_window_sec"]:
        if direction == "raise":
            _advance_raise_stage(
                rt,
                engine,
                now=now,
                vpd=vpd,
                improvement=improvement,
                settings=settings,
                availability=availability,
            )
        else:
            _advance_lower_stage(
                engine,
                now=now,
                vpd=vpd,
                improvement=improvement,
                settings=settings,
                availability=availability,
                outside_humidifying=outside_humidifying,
                preferred_temp=preferred_temp,
            )
        elapsed = 0.0
        improvement = 0.0

    stage = engine.get("stage") or "in_band"
    effective_target = _clip(
        engine.get("temp_target", base_target),
        settings["temp_min"],
        settings["temp_max"],
    )

    actions = {
        "fan": _fan_idle_action(rt),
        "heating": _thermostat_action(
            rt,
            temp=temp,
            target=effective_target,
            tolerance=float(st.live_state.get("temp_tol") or 0.2),
            temp_min=settings["temp_min"],
            temp_max=settings["temp_max"],
            reason=f"(VPD Temperaturziel {effective_target:.1f}°C)",
        ),
        "humidifier": _off_action(rt, "humidifier", "(VPD keine Befeuchtung)"),
        "dehumidifier": _off_action(rt, "dehumidifier", "(VPD keine Entfeuchtung)"),
    }

    if stage in {"exhaust", "heat", "dehumidify"} and availability["fan"] and outside_drying:
        actions["fan"] = _fan_regulation_action(
            rt,
            engine.get("fan_level"),
            "(VPD Außenluft trockener)",
        )

    if stage == "dehumidify" and availability["dehumidifier"]:
        actions["dehumidifier"] = _on_action(
            rt,
            "dehumidifier",
            "(VPD letzte Entfeuchtungsstufe)",
        )

    if stage in {"humidify", "humidify_outside"} and availability["humidifier"]:
        actions["humidifier"] = _on_action(
            rt,
            "humidifier",
            "(VPD zu hoch)",
        )

    if stage in {"outside_assist", "humidify_outside"} and availability["fan"] and outside_humidifying:
        actions["fan"] = _fan_regulation_action(
            rt,
            engine.get("fan_level"),
            "(VPD feuchtere Außenluft unterstützt)",
        )

    if stage in {"cool", "conserve"} and availability["fan"] and outside_lowering:
        actions["fan"] = _fan_regulation_action(
            rt,
            engine.get("fan_level"),
            "(VPD Temperatur bevorzugt senken)",
        )

    # Bei zu hohem VPD darf die normale Hysterese nicht weiterheizen und den
    # Dampfdruckdefizit dadurch noch vergrößern. Einzige Ausnahme bleibt die
    # explizite VPD-Temperatur-Untergrenze direkt darunter.
    if direction == "lower" and not temp_low:
        actions["heating"] = _off_action(
            rt,
            "heating",
            "(VPD zu hoch · Heizung pausiert)",
        )

    # Temperaturfenster besitzt Vorrang vor adaptiven Komfortschritten.
    if temp_low and availability["heating"]:
        effective_target = max(effective_target, settings["temp_min"])
        actions["heating"] = _on_action(rt, "heating", "(VPD Temperatur-Untergrenze)")
    elif temp_high:
        actions["heating"] = _off_action(rt, "heating", "(VPD Temperatur-Obergrenze)")
        if availability["fan"] and outside_cooling:
            actions["fan"] = _fan_regulation_action(
                rt,
                engine.get("fan_level"),
                "(VPD Außenluft kühlt)",
            )

    stage_labels = {
        "in_band": "Im Zielbereich",
        "exhaust": "Abluft prüfen",
        "heat": "Temperatur anheben",
        "dehumidify": "Entfeuchter",
        "cool": "Temperatur senken",
        "conserve": "Abluft und Heizung reduzieren",
        "humidify": "Luft befeuchten",
        "outside_assist": "Außenluft nutzen",
        "humidify_outside": "Befeuchten + Außenluft",
        "limited": "Keine weitere Aktorstufe",
    }

    next_step_label = _next_step_label(
        engine,
        settings=settings,
        availability=availability,
        outside_humidifying=outside_humidifying,
    )

    takeover = settings["mode"] == "AUTO"
    public = {
        "mode": settings["mode"],
        "active": True,
        "takeover": takeover,
        "ready": True,
        "fallback": False,
        "profile": profile,
        "stage": stage,
        "stage_label": stage_labels.get(stage, stage),
        "direction": engine.get("direction"),
        "reason": engine.get("last_transition_note") or stage_labels.get(stage, stage),
        "next_step_label": next_step_label,
        "vpd": round(vpd, 3),
        "target": round(target, 3),
        "tolerance": settings["tolerance"],
        "error": round(error, 3),
        "base_temp_target": round(base_target, 2),
        "preferred_temp_target": round(preferred_temp, 2),
        "effective_temp_target": round(effective_target, 2),
        "ramp": deepcopy(ramp),
        "range": {
            "temp_min": settings["temp_min"],
            "temp_max": settings["temp_max"],
            "hum_min": settings["hum_min"],
            "hum_max": settings["hum_max"],
        },
        "outside": {
            "temp": round(outside_temp, 2),
            "hum": round(outside_hum, 2),
            "inside_absolute_humidity": round(inside_ah, 2),
            "outside_absolute_humidity": round(outside_ah, 2),
            "drying": outside_drying,
            "humidifying": outside_humidifying,
            "cooling": outside_cooling,
            "lowering": outside_lowering,
            "vpd": round(outside_vpd, 3),
            "projected_exchange_vpd": round(projected_exchange_vpd, 3),
        },
        "effect": {
            "window_sec": settings["effect_window_sec"],
            "elapsed_sec": round(elapsed, 1),
            "improvement_kpa": round(improvement, 3),
            "minimum_kpa": settings["min_effect"],
            "next_evaluation_sec": max(
                0,
                int(round(settings["effect_window_sec"] - elapsed)),
            ) if direction and stage not in {"limited", "in_band"} else None,
        },
        "fan_level": engine.get("fan_level"),
        "managed_devices": managed_devices,
        "unavailable_devices": [
            device for device in VPD_MANAGED_DEVICES if not availability[device]
        ],
        "actions": deepcopy(actions),
    }

    with rt.state_lock:
        # Ein paralleler Sensor-/Profil-/Konfigurationswechsel erhöht die
        # Generation. Ein noch mit den alten Daten berechneter Plan darf den
        # dabei gesetzten sicheren Reset dann nicht wieder überschreiben.
        if st.live_state.get(_GENERATION_KEY, 0) == generation:
            st.live_state[_ENGINE_KEY] = engine
            st.live_state[_PUBLIC_KEY] = public
            st.live_state["vpd_base_temp_target"] = base_target
            st.live_state["vpd_temp_target"] = effective_target
            if takeover and availability["heating"]:
                st.live_state["temp_target"] = effective_target

    return public


def vpd_manages_device(device, runtime=None):
    rt = resolve_runtime(runtime)
    if device not in VPD_MANAGED_DEVICES:
        return False

    with rt.state_lock:
        public = rt.state.live_state.get(_PUBLIC_KEY)

    return bool(
        isinstance(public, dict)
        and public.get("takeover")
        and public.get("ready")
        and device in (public.get("managed_devices") or [])
        and isinstance((public.get("actions") or {}).get(device), dict)
    )


def apply_vpd_device_plan(device, runtime=None):
    """Wendet genau einen vorbereiteten Plan über den bestehenden Aktorpfad an."""

    rt = resolve_runtime(runtime)
    with rt.state_lock:
        public = deepcopy(rt.state.live_state.get(_PUBLIC_KEY) or {})

    action = (public.get("actions") or {}).get(device)
    if not isinstance(action, dict):
        return None

    return apply_device_state(
        device,
        action,
        runtime=rt,
        reason=str(action.get("reason") or "(VPD AUTO)"),
    )


__all__ = (
    "VPD_CONTROL_MODES",
    "VPD_MANAGED_DEVICES",
    "apply_vpd_device_plan",
    "reset_vpd_control",
    "update_vpd_control",
    "validate_vpd_environment_alignment",
    "vpd_manages_device",
)
