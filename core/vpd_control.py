"""Intelligente, stationsbezogene VPD-Regelung.

Die VPD-Regelung ist ein Koordinator oberhalb der bestehenden ENV-Gerätepfade.
Sie umgeht weder Shelly-Power, Controller-Validierung, Shadow-Gates noch den
Safety-Supervisor. Nur Geräte, die ausdrücklich im Modus ``ENV`` stehen,
können im AUTO-Modus übernommen werden.

Regelstrategie bei zu niedrigem VPD / zu hoher Feuchte:

1. Abluft nur einsetzen, wenn die Außenluft tatsächlich trockener ist.
2. Jede erlaubte Abluftstufe über ein konfigurierbares Zeitfenster prüfen.
3. Anschließend den Temperatur-Sollwert schrittweise bis zur Phasengrenze
   anheben; eine einzelne schwache VPD-Reaktion beendet diesen Weg nicht.
4. Erst wenn Abluft- und Temperaturweg ausgeschöpft oder technisch ohne
   Reaktion sind, den Entfeuchter anfordern.

Bei zu hohem VPD wird dagegen zuerst das Temperaturziel innerhalb des
phasenbezogenen Min-/Max-Fensters abgesenkt. Geeignete kühlere Außenluft darf
diesen Schritt unterstützen; erst danach folgen Befeuchtungsschritte.

Eine aktivierte Profilrampe interpoliert im intelligenten Modus VPD-Ziel,
Toleranz und Klimafenster. Klassische DAY_TEMP/NIGHT_TEMP-Werte sind keine
Regelbasis des VPD-Koordinators mehr.

Temperatur und Luftfeuchtigkeit werden dabei nicht als zwei unabhängige
Sollwerte behandelt. Der Koordinator berechnet zu jedem VPD-Temperaturziel den
passenden Feuchtesollwert. Die konfigurierten Temperatur- und Feuchtespannen
sind harte phasenbezogene Grenzen. Ein mathematischer VPD-Feuchtewert außerhalb
dieser Spanne bleibt reine Diagnose und wird niemals als Sollwert veröffentlicht.

Der MONITOR-Modus berechnet exakt denselben Plan, übernimmt aber keine Aktoren.

Die Sensor-, Zielband- und Sicherheitsprüfung läuft bei jedem Hauptzyklus.
Lediglich der nächste Aktorschritt wird adaptiv freigegeben: neue Strategien
starten mit 60 Sekunden, träge oder bereits beruhigte Situationen werden über
120 Sekunden bewertet und erst nach zehn stabilen Minuten darf das bestehende
konfigurierbare Wirkungsfenster als längerer Prüftakt genutzt werden.
"""

from __future__ import annotations

from copy import deepcopy
import math
from statistics import median
import time

from core.capability_routing import controller_assignment_for_config
from core.controller_states import apply_device_state, resolve_control_state
from core.controller_setpoints import controller_schema_for_family
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


_FAST_EFFECT_WINDOW_SEC = 60
_SETTLING_EFFECT_WINDOW_SEC = 120
_STABLE_AFTER_SEC = 600


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

    # Im ausdrücklich aktivierten VPD-AUTO-Modus ist der gespeicherte
    # ENV-Wert die normale Regelleistung, nicht automatisch die technische
    # Obergrenze. Bei einer gültigen Spider-Farmer-Abluftzuordnung darf der
    # Koordinator deshalb innerhalb des bekannten Blower-Schemas bis 100 %
    # staffeln. Ohne bestätigte Zuordnung bleibt der bisherige, konservative
    # ENV-Wert die Grenze.
    try:
        assignment = controller_assignment_for_config(runtime.config, "fan")
    except (TypeError, ValueError):
        assignment = None
    if (
        env_level is not None
        and isinstance(assignment, dict)
        and assignment.get("provider") == "spiderfarmer"
        and assignment.get("target_id")
    ):
        level_schema = controller_schema_for_family(
            "blower",
            ("level",),
        ).get("level") or {}
        try:
            physical_min = int(level_schema["min"])
            physical_max = int(level_schema["max"])
        except (KeyError, TypeError, ValueError):
            physical_min = physical_max = None

        if physical_min is not None and physical_max is not None:
            minimum = max(physical_min, int(minimum))
            maximum = max(int(maximum), physical_max)

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

    # Der UI-Wert "Abluft-Schritt %" bezeichnet Prozentpunkte der
    # Blower-Leistung. 10 bedeutet damit nachvollziehbar 75 -> 85 und nicht
    # zehn Prozent des noch konfigurierten Regelbands.
    increment = max(1, int(math.ceil(float(step_percent))))
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


def _set_stage(engine, *, direction, stage, now, vpd, temp=None, note=None):
    recorded_temp = temp if temp is not None else engine.get("last_temp")
    event = {
        "at": float(now),
        "direction": direction,
        "stage": stage,
        "note": str(note or ""),
        "vpd": round(float(vpd), 3),
    }
    try:
        event["temp"] = round(float(recorded_temp), 2)
    except (TypeError, ValueError):
        event["temp"] = None
    try:
        event["fan_level"] = int(engine.get("fan_level"))
    except (TypeError, ValueError):
        event["fan_level"] = None
    try:
        event["temp_target"] = round(float(engine.get("temp_target")), 2)
    except (TypeError, ValueError):
        event["temp_target"] = None

    events = list(engine.get("events") or [])
    events.append(event)
    engine["events"] = events[-30:]

    engine["direction"] = direction
    engine["stage"] = stage
    engine["stage_started_at"] = float(now)
    engine["samples"] = [(float(now), float(vpd))]
    if temp is not None:
        engine["stage_start_temp"] = float(temp)
    engine["last_transition_note"] = note

    try:
        fan_signature = int(engine.get("fan_level"))
    except (TypeError, ValueError):
        fan_signature = None
    try:
        temp_signature = round(float(engine.get("temp_target")), 3)
    except (TypeError, ValueError):
        temp_signature = None
    signature = f"{direction}|{stage}|{fan_signature}|{temp_signature}"
    if signature != engine.get("_cadence_signature"):
        engine["_cadence_signature"] = signature
        engine["_cadence_force_fast"] = True
        engine.pop("_cadence_window_sec", None)
        engine.pop("_cadence_phase", None)


def _remember_evaluation(engine, *, now, improvement):
    engine["last_evaluation_at"] = float(now)
    engine["last_evaluation_improvement"] = float(improvement)


def _adaptive_effect_window(
    engine,
    *,
    now,
    direction,
    error,
    tolerance,
    max_window_sec,
):
    """Wählt das Wirkungsfenster, ohne die laufende Sicherheitsprüfung zu drosseln."""

    maximum = max(
        _FAST_EFFECT_WINDOW_SEC,
        int(round(float(max_window_sec))),
    )
    fast = min(_FAST_EFFECT_WINDOW_SEC, maximum)
    settling = min(_SETTLING_EFFECT_WINDOW_SEC, maximum)

    if direction is None:
        try:
            stable_since = float(engine.get("stable_since"))
        except (TypeError, ValueError):
            stable_since = float(now)
            engine["stable_since"] = stable_since

        stable_elapsed = max(0.0, float(now) - stable_since)
        engine.pop("_cadence_window_sec", None)
        engine.pop("_cadence_phase", None)
        engine.pop("_cadence_force_fast", None)

        if stable_elapsed < fast:
            phase = "fast"
            label = "Schnellprüfung"
            interval = fast
        elif stable_elapsed < _STABLE_AFTER_SEC:
            phase = "settling"
            label = "Beruhigungsphase"
            interval = settling
        else:
            phase = "stable"
            label = "Stabilbetrieb"
            interval = maximum
    else:
        engine.pop("stable_since", None)
        stable_elapsed = 0.0

        interval = engine.get("_cadence_window_sec")
        phase = engine.get("_cadence_phase")
        try:
            interval = int(interval)
        except (TypeError, ValueError):
            interval = None

        if interval is None or interval <= 0:
            force_fast = bool(engine.pop("_cadence_force_fast", False))
            deviation = abs(float(error))
            near_target = deviation <= max(0.001, float(tolerance) * 2.0)
            heat_is_stalling = (
                engine.get("stage") == "heat"
                and int(engine.get("heat_stall_windows") or 0) > 0
            )

            if force_fast or (not near_target and not heat_is_stalling):
                phase = "fast"
                interval = fast
            else:
                phase = "settling"
                interval = settling

            engine["_cadence_window_sec"] = interval
            engine["_cadence_phase"] = phase

        label = (
            "Schnellprüfung"
            if phase == "fast"
            else "Beruhigungsphase"
        )

    return {
        "adaptive": True,
        "phase": phase,
        "label": label,
        "interval_sec": int(interval),
        "max_interval_sec": int(maximum),
        "stable_after_sec": _STABLE_AFTER_SEC,
        "stable_elapsed_sec": round(stable_elapsed, 1),
        "continuous_guard": True,
    }


def _temperature_response(engine, temp, settings):
    try:
        start_temp = float(engine.get("stage_start_temp"))
    except (TypeError, ValueError):
        start_temp = float(temp)

    change = float(temp) - start_temp
    # Kleine Sensorschwankungen sollen nicht als Heizwirkung gelten. Bei sehr
    # kleinen konfigurierten Sollwertschritten bleibt die Schwelle dennoch
    # erreichbar.
    threshold = min(0.10, max(0.03, float(settings["temp_step"]) * 0.20))
    return change, change >= threshold


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


def _restore_classic_live_targets(state):
    """Entfernt VPD-Sollwerte und stellt vorhandene Profilwerte wieder her."""

    live = state.live_state
    for target_key, climate_key in (
        ("temp_target", "climate_temp_target"),
        ("hum_target", "climate_hum_target"),
    ):
        try:
            value = float(live.get(climate_key))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            live[target_key] = value

    try:
        climate_hum_tol = float(live.get("climate_hum_tol"))
    except (TypeError, ValueError):
        climate_hum_tol = None
    if climate_hum_tol is not None and math.isfinite(climate_hum_tol):
        live["hum_tol"] = climate_hum_tol

    for key in (
        "vpd_temp_target",
        "vpd_base_temp_target",
        "vpd_hum_target",
        "vpd_effective_target",
    ):
        live.pop(key, None)


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


def _temperature_for_vpd_exact(target_vpd, humidity):
    """Unbegrenzte Temperatur, die bei ``humidity`` den Ziel-VPD ergibt."""

    humidity = _clip(humidity, 0.0, 99.9)
    vapor_fraction = 1.0 - humidity / 100.0
    if vapor_fraction <= 0.0:
        return float("inf")

    saturation_target = float(target_vpd) / vapor_fraction
    if saturation_target <= 0.0:
        return float("-inf")

    logarithm = math.log(saturation_target / 0.6108)
    denominator = 17.27 - logarithm
    if abs(denominator) < 1e-9:
        return float("inf")

    return 237.3 * logarithm / denominator


def _temperature_for_vpd(target_vpd, humidity, temp_min, temp_max):
    """Temperatur, die beim aktuellen RH rechnerisch den Ziel-VPD ergibt."""

    return _clip(
        _temperature_for_vpd_exact(target_vpd, humidity),
        temp_min,
        temp_max,
    )


def _humidity_for_vpd(target_vpd, temperature):
    """Relative Feuchte für einen VPD-Zielwert bei gegebener Temperatur."""

    saturation = _saturation_vapor_pressure(temperature)
    if saturation <= 0.0:
        return 0.0
    return _clip(100.0 * (1.0 - float(target_vpd) / saturation), 0.0, 100.0)


def _coupled_target_curve(settings):
    """Erreichbarer Abschnitt der Ziel-VPD-Kurve in den harten Klimagrenzen."""

    attainable_min = float(
        calculate_vpd(settings["temp_min"], settings["hum_max"])
    )
    attainable_max = float(
        calculate_vpd(settings["temp_max"], settings["hum_min"])
    )
    effective_vpd = _clip(
        settings["target"],
        attainable_min,
        attainable_max,
    )

    temperature_at_hum_min = _temperature_for_vpd_exact(
        effective_vpd,
        settings["hum_min"],
    )
    temperature_at_hum_max = _temperature_for_vpd_exact(
        effective_vpd,
        settings["hum_max"],
    )
    curve_min = max(
        float(settings["temp_min"]),
        min(temperature_at_hum_min, temperature_at_hum_max),
    )
    curve_max = min(
        float(settings["temp_max"]),
        max(temperature_at_hum_min, temperature_at_hum_max),
    )

    # An einem exakt erreichbaren Eckpunkt können Rundungsreste die beiden
    # Grenzen um wenige Femtograd vertauschen. Dieser Fall bleibt ein einzelner
    # gültiger Zielpunkt und darf nicht zu einem leeren Regelband werden.
    if curve_min > curve_max:
        midpoint = _clip(
            (curve_min + curve_max) / 2.0,
            settings["temp_min"],
            settings["temp_max"],
        )
        curve_min = curve_max = midpoint

    return {
        "vpd": effective_vpd,
        "requested_vpd": float(settings["target"]),
        "temp_min": curve_min,
        "temp_max": curve_max,
        "attainable_min": attainable_min,
        "attainable_max": attainable_max,
    }


def _coupled_setpoints(settings, curve, temperature):
    """Gemeinsames Live-Zielpaar innerhalb der harten Feuchtegrenzen."""

    target_temp = _clip(
        temperature,
        settings["temp_min"],
        settings["temp_max"],
    )
    target_vpd = float(settings["target"])
    calculated_hum = _humidity_for_vpd(
        target_vpd,
        target_temp,
    )
    target_hum = _clip(
        calculated_hum,
        settings["hum_min"],
        settings["hum_max"],
    )

    lower_vpd = max(
        0.001,
        float(settings["target"]) - float(settings["tolerance"]),
    )
    upper_vpd = float(settings["target"]) + float(settings["tolerance"])
    calculated_band_hum_min = _humidity_for_vpd(upper_vpd, target_temp)
    calculated_band_hum_max = _humidity_for_vpd(lower_vpd, target_temp)
    band_hum_min = _clip(
        calculated_band_hum_min,
        settings["hum_min"],
        settings["hum_max"],
    )
    band_hum_max = _clip(
        calculated_band_hum_max,
        settings["hum_min"],
        settings["hum_max"],
    )

    max_temp_hum = _humidity_for_vpd(
        settings["target"],
        settings["temp_max"],
    )
    max_temp_compatible = (
        float(settings["hum_min"]) - 1e-9
        <= max_temp_hum
        <= float(settings["hum_max"]) + 1e-9
    )

    calculated_hum_compatible = (
        float(settings["hum_min"]) - 1e-9
        <= calculated_hum
        <= float(settings["hum_max"]) + 1e-9
    )

    explanations = []
    if not calculated_hum_compatible:
        relation = "oberhalb" if calculated_hum > settings["hum_max"] else "unterhalb"
        hard_limit = (
            float(settings["hum_max"])
            if calculated_hum > settings["hum_max"]
            else float(settings["hum_min"])
        )
        explanations.append(
            f"Bei {target_temp:.1f} °C gehören zum VPD-Ziel "
            f"rechnerisch {calculated_hum:.1f} %; dieser Wert liegt {relation} "
            "der verbindlichen Feuchtegrenze. Der veröffentlichte "
            f"Feuchtesollwert bleibt deshalb auf {hard_limit:.1f} % begrenzt."
        )
    else:
        explanations.append(
            "Temperatur und berechneter Feuchtesollwert liegen gemeinsam im "
            "verbindlichen VPD-Klimafenster."
        )
    if not max_temp_compatible:
        explanations.append(
            f"Bei der erlaubten Temperatur-Obergrenze von "
            f"{float(settings['temp_max']):.1f} °C gehören rechnerisch "
            f"{max_temp_hum:.1f} % zu {target_vpd:.2f} kPa. Dieser Rechenwert "
            "überschreibt die konfigurierte Feuchtegrenze nicht."
        )

    return {
        "vpd": target_vpd,
        "temp": target_temp,
        "hum": target_hum,
        "calculated_hum": calculated_hum,
        "hum_band_min": band_hum_min,
        "hum_band_max": band_hum_max,
        "calculated_hum_band_min": calculated_band_hum_min,
        "calculated_hum_band_max": calculated_band_hum_max,
        "curve_temp_min": float(curve["temp_min"]),
        "curve_temp_max": float(curve["temp_max"]),
        "at_temp_max": {
            "temp": float(settings["temp_max"]),
            "hum": _clip(
                max_temp_hum,
                settings["hum_min"],
                settings["hum_max"],
            ),
            "calculated_hum": max_temp_hum,
            "within_humidity_range": max_temp_compatible,
        },
        "within_humidity_range": calculated_hum_compatible,
        "constrained": not calculated_hum_compatible,
        "explanation": " ".join(explanations),
    }


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
        "events": [],
    }


def _next_step_label(
    engine,
    *,
    settings,
    availability,
    outside_drying,
    outside_humidifying,
):
    """Beschreibt ausschließlich den im Zustandsautomaten möglichen Folgeschritt."""

    direction = engine.get("direction")
    stage = engine.get("stage") or "in_band"

    if direction is None or stage == "in_band":
        return "Zielband halten und Klima weiter beobachten"
    if direction == "raise":
        fan_level = engine.get("fan_level")
        fan_max = engine.get("fan_max")
        temp_target = float(engine.get("temp_target") or settings["temp_min"])

        if stage == "limited":
            if bool(engine.get("fan_sweep_complete")):
                fan_text = (
                    f"Abluft {int(fan_level)}/{int(fan_max)} ausgeschöpft"
                    if fan_level is not None and fan_max is not None
                    else "Abluftweg ausgeschöpft"
                )
            elif not outside_drying:
                fan_text = "Außenluft derzeit nicht zum Trocknen geeignet"
            else:
                fan_text = "Abluft derzeit nicht regelbar"
            temp_text = (
                f"Temperaturziel {temp_target:.1f}/{settings['temp_max']:.1f} °C ausgeschöpft"
                if bool(engine.get("heat_sweep_complete"))
                else f"Temperaturweg bis {settings['temp_max']:.1f} °C derzeit nicht verfügbar"
            )
            return (
                f"{fan_text}; {temp_text}; Verfügbarkeit und Klima erneut prüfen"
            )
        if stage == "exhaust":
            if not availability["fan"] or not outside_drying:
                if availability["heating"] and temp_target < settings["temp_max"]:
                    return "Außenluft nicht mehr geeignet; anschließend zur Temperaturregelung wechseln"
                if availability["dehumidifier"]:
                    return "Außenluft nicht mehr geeignet; anschließend den Entfeuchter zuschalten"
                return "Außenluft neu bewerten und sichere Grenzen halten"
            if fan_level is not None and fan_max is not None and fan_level < fan_max:
                next_level = _next_fan_level(
                    fan_level,
                    engine.get("fan_min"),
                    fan_max,
                    settings["fan_step"],
                )
                return (
                    f"Abluftstufe {int(fan_level)} prüfen; danach auf "
                    f"{int(next_level)} von maximal {int(fan_max)} erhöhen"
                )
            if availability["heating"] and temp_target < settings["temp_max"]:
                next_target = min(
                    settings["temp_max"],
                    max(temp_target, float(engine.get("last_temp") or temp_target))
                    + settings["temp_step"],
                )
                return (
                    f"Abluft-Maximum vollständig prüfen; danach Temperaturziel "
                    f"auf {next_target:.1f} °C anheben"
                )
            if availability["dehumidifier"]:
                return "Abluft-Maximum vollständig prüfen; danach den Entfeuchter zuschalten"
            return "Abluft-Maximum vollständig prüfen und anschließend Grenzen neu bewerten"
        if stage == "heat":
            if temp_target < settings["temp_max"]:
                next_target = min(
                    settings["temp_max"],
                    temp_target + settings["temp_step"],
                )
                return (
                    f"Temperaturziel {temp_target:.1f} °C erreichen und danach "
                    f"auf {next_target:.1f} °C erhöhen (maximal {settings['temp_max']:.1f} °C)"
                )
            if availability["dehumidifier"]:
                return "Temperatur-Maximum vollständig prüfen; danach den Entfeuchter zuschalten"
            return "Temperatur-Maximum vollständig prüfen und anschließend sicher halten"
        if stage == "dehumidify":
            return "Entfeuchterwirkung bis zum VPD-Zielband weiter prüfen"

    if direction == "lower":
        if stage == "limited":
            return "Auf eine Klimaänderung oder eine weitere ENV-Aktorstufe warten"
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
    temp,
    improvement,
    settings,
    availability,
    outside_drying,
):
    stage = engine.get("stage")
    min_effect = settings["min_effect"]
    _remember_evaluation(engine, now=now, improvement=improvement)

    if stage == "exhaust":
        current = engine.get("fan_level")
        minimum = engine.get("fan_min")
        maximum = engine.get("fan_max")

        # Solange die Außenluft geeignet ist, bekommt jede konfigurierte
        # Abluftstufe ihr eigenes vollständiges Wirkungsfenster. Auch ein noch
        # schwacher Einzelwert darf den Abluftweg nicht vorschnell abbrechen.
        if (
            availability["fan"]
            and outside_drying
            and current is not None
            and maximum is not None
            and current < maximum
        ):
            next_level = _next_fan_level(
                current,
                minimum,
                maximum,
                settings["fan_step"],
            )
            engine["fan_level"] = next_level
            effect_text = (
                "wirkt"
                if improvement >= min_effect
                else "wirkt bisher noch zu schwach"
            )
            _set_stage(
                engine,
                direction="raise",
                stage="exhaust",
                now=now,
                vpd=vpd,
                temp=temp,
                note=(
                    f"Abluft {effect_text}; Stufe {int(next_level)} von "
                    f"maximal {int(maximum)} wird jetzt geprüft"
                ),
            )
            return

        # Die aktuell höchste Stufe wurde bereits ein volles Zeitfenster lang
        # geprüft. Erst jetzt ist der Abluftweg tatsächlich ausgeschöpft.
        if availability["fan"] and outside_drying:
            engine["fan_sweep_complete"] = True

        if availability["heating"] and engine.get("temp_target", 0) < settings["temp_max"]:
            engine["temp_target"] = min(
                settings["temp_max"],
                max(
                    float(engine.get("temp_target") or settings["temp_min"]),
                    float(temp),
                )
                + settings["temp_step"],
            )
            engine["heat_stall_windows"] = 0
            _set_stage(
                engine,
                direction="raise",
                stage="heat",
                now=now,
                vpd=vpd,
                temp=temp,
                note=(
                    "Abluftweg ausgeschöpft; Temperaturziel wird auf "
                    f"{engine['temp_target']:.1f} °C angehoben"
                ),
            )
        elif availability["dehumidifier"]:
            if (
                float(engine.get("temp_target") or settings["temp_min"])
                >= settings["temp_max"]
            ):
                engine["heat_sweep_complete"] = True
            _set_stage(
                engine,
                direction="raise",
                stage="dehumidify",
                now=now,
                vpd=vpd,
                temp=temp,
                note="Abluftweg ausgeschöpft und keine Temperaturreserve; Entfeuchter angefordert",
            )
        else:
            if (
                float(engine.get("temp_target") or settings["temp_min"])
                >= settings["temp_max"]
            ):
                engine["heat_sweep_complete"] = True
            _set_stage(
                engine,
                direction="raise",
                stage="limited",
                now=now,
                vpd=vpd,
                temp=temp,
                note="Abluftweg ausgeschöpft; keine weitere sichere VPD-Stufe verfügbar",
            )
        return

    if stage == "heat":
        current_target = float(engine.get("temp_target") or settings["temp_min"])
        temp_change, heating_responded = _temperature_response(
            engine,
            temp,
            settings,
        )
        reach_tolerance = min(
            0.30,
            max(0.15, float(settings["temp_step"]) / 2.0),
        )
        target_reached = float(temp) >= current_target - reach_tolerance

        if target_reached and current_target < settings["temp_max"]:
            engine["temp_target"] = min(
                settings["temp_max"],
                current_target + settings["temp_step"],
            )
            engine["heat_stall_windows"] = 0
            _set_stage(
                engine,
                direction="raise",
                stage="heat",
                now=now,
                vpd=vpd,
                temp=temp,
                note=(
                    f"Temperaturstufe {current_target:.1f} °C erreicht; "
                    f"{engine['temp_target']:.1f} °C wird jetzt geprüft"
                ),
            )
            return

        if not target_reached:
            if heating_responded:
                engine["heat_stall_windows"] = 0
                note = (
                    f"Heizung reagiert ({temp_change:+.1f} °C); Temperaturziel "
                    f"{current_target:.1f} °C wird weiter angefahren"
                )
            else:
                stall_windows = int(engine.get("heat_stall_windows") or 0) + 1
                engine["heat_stall_windows"] = stall_windows
                if stall_windows < 2:
                    note = (
                        f"Temperaturziel {current_target:.1f} °C noch nicht erreicht; "
                        "ein zweites Prüfintervall folgt"
                    )
                else:
                    engine["heat_sweep_complete"] = True
                    if availability["dehumidifier"]:
                        _set_stage(
                            engine,
                            direction="raise",
                            stage="dehumidify",
                            now=now,
                            vpd=vpd,
                            temp=temp,
                            note=(
                                "Heizung reagiert über zwei Prüfintervalle nicht; "
                                "Entfeuchter angefordert"
                            ),
                        )
                    else:
                        _set_stage(
                            engine,
                            direction="raise",
                            stage="limited",
                            now=now,
                            vpd=vpd,
                            temp=temp,
                            note=(
                                "Heizung reagiert über zwei Prüfintervalle nicht; "
                                "kein Entfeuchter im ENV-Modus"
                            ),
                        )
                    return

            _set_stage(
                engine,
                direction="raise",
                stage="heat",
                now=now,
                vpd=vpd,
                temp=temp,
                note=note,
            )
            return

        # Das erlaubte Temperatur-Maximum wurde erreicht und ein komplettes
        # Wirkungsfenster lang gehalten. Erst danach folgt die letzte Stufe.
        engine["heat_sweep_complete"] = True
        if availability["dehumidifier"]:
            _set_stage(
                engine,
                direction="raise",
                stage="dehumidify",
                now=now,
                vpd=vpd,
                temp=temp,
                note="Temperatur-Maximum ausgeschöpft; Entfeuchter angefordert",
            )
        else:
            _set_stage(
                engine,
                direction="raise",
                stage="limited",
                now=now,
                vpd=vpd,
                temp=temp,
                note="Temperatur-Maximum ausgeschöpft; kein Entfeuchter im ENV-Modus",
            )
        return

    if stage == "dehumidify":
        # Die letzte Stufe bleibt aktiv, bis das Zielband erreicht ist. Das
        # eigentliche Abschalten erfolgt dann sofort über den in-band-Pfad.
        if availability["dehumidifier"]:
            _set_stage(
                engine,
                direction="raise",
                stage="dehumidify",
                now=now,
                vpd=vpd,
                temp=temp,
                note="Entfeuchterwirkung wird weiter beobachtet",
            )
        else:
            _set_stage(
                engine,
                direction="raise",
                stage="limited",
                now=now,
                vpd=vpd,
                temp=temp,
                note="Entfeuchter ist nicht mehr im ENV-Modus; sichere Grenzen werden gehalten",
            )
        return

    if stage == "limited":
        # LIMITED ist kein totes Ende. Änderungen an Außenklima oder
        # Geräteverfügbarkeit werden in jedem Prüfintervall neu bewertet.
        if (
            availability["fan"]
            and outside_drying
            and not bool(engine.get("fan_sweep_complete"))
        ):
            _set_stage(
                engine,
                direction="raise",
                stage="exhaust",
                now=now,
                vpd=vpd,
                temp=temp,
                note="Trockene Außenluft ist wieder nutzbar; Abluftweg wird erneut geprüft",
            )
        elif (
            availability["heating"]
            and not bool(engine.get("heat_sweep_complete"))
            and float(engine.get("temp_target") or settings["temp_min"])
            < settings["temp_max"]
        ):
            engine["temp_target"] = min(
                settings["temp_max"],
                max(
                    float(engine.get("temp_target") or settings["temp_min"]),
                    float(temp),
                ) + settings["temp_step"],
            )
            engine["heat_stall_windows"] = 0
            _set_stage(
                engine,
                direction="raise",
                stage="heat",
                now=now,
                vpd=vpd,
                temp=temp,
                note=f"Temperaturweg ist wieder verfügbar; {engine['temp_target']:.1f} °C wird geprüft",
            )
        elif availability["dehumidifier"]:
            _set_stage(
                engine,
                direction="raise",
                stage="dehumidify",
                now=now,
                vpd=vpd,
                temp=temp,
                note="Entfeuchter ist jetzt verfügbar und wird angefordert",
            )
        else:
            _set_stage(
                engine,
                direction="raise",
                stage="limited",
                now=now,
                vpd=vpd,
                temp=temp,
                note="Sichere Abluft- und Temperaturgrenzen bleiben ausgeschöpft",
            )


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
    _remember_evaluation(engine, now=now, improvement=improvement)

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
            "events": [],
        }
        with rt.state_lock:
            st.live_state[_PUBLIC_KEY] = public
            st.live_state.pop(_ENGINE_KEY, None)
            _restore_classic_live_targets(st)
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
            "events": [],
        }
        with rt.state_lock:
            st.live_state[_PUBLIC_KEY] = public
            st.live_state.pop(_ENGINE_KEY, None)
            _restore_classic_live_targets(st)
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
            "events": [],
        }
        with rt.state_lock:
            st.live_state[_PUBLIC_KEY] = public
            st.live_state.pop(_ENGINE_KEY, None)
            _restore_classic_live_targets(st)
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
        previous_public = deepcopy(st.live_state.get(_PUBLIC_KEY) or {})

    blockers = _readiness(rt, values)
    if blockers:
        public = _public_waiting_state(
            settings,
            profile,
            values,
            blockers,
            ramp,
        )
        public["events"] = deepcopy(
            list(previous_public.get("events") or [])[-20:]
        )
        with rt.state_lock:
            st.live_state[_PUBLIC_KEY] = public
            st.live_state.pop(_ENGINE_KEY, None)
            _restore_classic_live_targets(st)
        return public

    temp = float(values["temp"])
    hum = float(values["hum"])
    outside_temp = float(values["outside_temp"])
    outside_hum = float(values["outside_hum"])
    vpd = float(calculate_vpd(temp, hum))
    target = settings["target"]
    error = vpd - target
    target_curve = _coupled_target_curve(settings)
    regulation_settings = dict(settings)
    # Temperatur- und Feuchtefenster bleiben eigenständige harte Grenzen. Für
    # den Heiz-/Kühlweg gelten die VPD-Temperaturgrenzen; ein dabei errechneter
    # Feuchtewert wird separat auf die VPD-Feuchtegrenzen begrenzt.
    regulation_settings["target"] = target

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

    base_target = _clip(
        _base_temp_target(rt, settings, current_temp=temp),
        settings["temp_min"],
        settings["temp_max"],
    )
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
        # Der Zustandsautomat startet beim Tag-/Nachtwechsel bewusst neu. Der
        # kurze Diagnoseverlauf bleibt erhalten, damit die Regellog-Seite den
        # Übergang weiterhin nachvollziehbar darstellen kann.
        previous_events = list(engine.get("events") or [])[-30:]
        engine = {"events": previous_events}
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
    elif fan_limits["minimum"] is not None and fan_limits["maximum"] is not None:
        engine["fan_level"] = int(
            _clip(
                engine["fan_level"],
                fan_limits["minimum"],
                fan_limits["maximum"],
            )
        )
    else:
        engine["fan_level"] = None

    low_needed = vpd < target - settings["tolerance"]
    high_needed = vpd > target + settings["tolerance"]
    humidity_too_high = hum > settings["hum_max"]
    humidity_too_low = hum < settings["hum_min"]
    temp_low = temp < settings["temp_min"]
    temp_high = temp > settings["temp_max"]

    # Phasenbezogene Feuchte-Min/Max-Werte sind verbindlich. Eine Verletzung
    # dieser Grenzen hat Vorrang vor dem Komfort-Zielband des VPD. Innerhalb
    # des Klimafensters bleibt der gemessene VPD die führende Regelgröße.
    if humidity_too_high:
        direction_note = (
            f"Luftfeuchtigkeit {hum:.1f} % liegt über der verbindlichen "
            f"Obergrenze von {settings['hum_max']:.1f} %"
        )
        if high_needed:
            direction_note += "; Heizen bleibt wegen des bereits zu hohen VPD gesperrt"
        elif low_needed:
            direction_note += "; VPD ist gleichzeitig zu niedrig"
    elif humidity_too_low:
        direction_note = (
            f"Luftfeuchtigkeit {hum:.1f} % liegt unter der verbindlichen "
            f"Untergrenze von {settings['hum_min']:.1f} %"
        )
        if low_needed:
            direction_note += "; weiteres Trocknen bleibt gesperrt"
        elif high_needed:
            direction_note += "; VPD ist gleichzeitig zu hoch"
    elif low_needed:
        direction_note = "VPD ist zu niedrig"
    elif high_needed:
        direction_note = "VPD ist zu hoch"
    else:
        direction_note = "VPD und Feuchtigkeit sind im Zielbereich"

    if humidity_too_high:
        direction = "raise"
        control_goal = "humidity_high"
    elif humidity_too_low:
        direction = "lower"
        control_goal = "humidity_low"
    elif low_needed:
        direction = "raise"
        control_goal = "vpd_raise"
    elif high_needed:
        direction = "lower"
        control_goal = "vpd_lower"
    else:
        direction = None
        control_goal = "in_band"

    # Eine Feuchteüberschreitung darf nur dann über Erwärmung behandelt
    # werden, wenn auch der VPD tatsächlich noch unter seinem Zielband liegt.
    # Bei bereits passendem oder zu hohem VPD bleiben nur echte
    # Entfeuchtungswege zulässig.
    raise_availability = dict(availability)
    raise_availability["heating"] = bool(
        availability["heating"] and low_needed
    )

    direction_changed = (
        direction != engine.get("direction")
        or control_goal != engine.get("control_goal")
    )
    if direction_changed:
        engine["temp_target"] = base_target
        engine["fan_level"] = fan_limits["minimum"]
        engine["fan_sweep_complete"] = False
        engine["heat_sweep_complete"] = False
        engine["heat_stall_windows"] = 0
        engine.pop("last_evaluation_at", None)
        engine.pop("last_evaluation_improvement", None)
        engine["control_goal"] = control_goal

        if direction == "raise":
            if raise_availability["fan"] and outside_drying:
                initial_stage = "exhaust"
            elif (
                raise_availability["heating"]
                and temp < regulation_settings["temp_max"]
            ):
                initial_stage = "heat"
                engine["temp_target"] = min(
                    regulation_settings["temp_max"],
                    max(base_target, temp) + settings["temp_step"],
                )
            elif raise_availability["dehumidifier"]:
                initial_stage = "dehumidify"
            else:
                initial_stage = "limited"
            _set_stage(
                engine,
                direction="raise",
                stage=initial_stage,
                now=now,
                vpd=vpd,
                temp=temp,
                note=direction_note,
            )
        elif direction == "lower":
            temperature_path_available = bool(
                availability["heating"]
                or (availability["fan"] and outside_lowering)
            )
            if humidity_too_low and availability["humidifier"]:
                initial_stage = "humidify"
                note = f"{direction_note}; Luftbefeuchter wird angefordert"
            elif humidity_too_low and availability["fan"] and outside_humidifying:
                initial_stage = "outside_assist"
                note = f"{direction_note}; feuchtere Außenluft unterstützt"
            elif (
                temperature_path_available
                and preferred_temp < base_target - 0.01
            ):
                engine["temp_target"] = _step_temperature(
                    base_target,
                    preferred_temp,
                    settings["temp_step"],
                )
                initial_stage = "cool"
                note = f"{direction_note}; Temperatur wird bevorzugt abgesenkt"
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
                temp=temp,
                note=note,
            )
        else:
            _set_stage(
                engine,
                direction=None,
                stage="in_band",
                now=now,
                vpd=vpd,
                temp=temp,
                note=direction_note,
            )
    else:
        engine["control_goal"] = control_goal

    # Ändert sich während einer Feuchteüberschreitung der VPD so weit, dass
    # weiteres Heizen widersprüchlich wäre, wird die Heizstufe sofort beendet.
    # Die harte Feuchtegrenze bleibt anschließend über Abluft/Entfeuchter aktiv.
    if (
        direction == "raise"
        and engine.get("stage") == "heat"
        and not raise_availability["heating"]
    ):
        engine["temp_target"] = _clip(
            temp,
            settings["temp_min"],
            settings["temp_max"],
        )
        next_stage = (
            "dehumidify"
            if raise_availability["dehumidifier"]
            else "limited"
        )
        note = (
            "Feuchte bleibt über der Obergrenze; Heizung wird am VPD-Ziel beendet und der Entfeuchter angefordert"
            if next_stage == "dehumidify"
            else "Feuchte bleibt über der Obergrenze; Heizung wird am VPD-Ziel beendet, kein weiterer Entfeuchtungsaktor verfügbar"
        )
        _set_stage(
            engine,
            direction="raise",
            stage=next_stage,
            now=now,
            vpd=vpd,
            temp=temp,
            note=note,
        )
    cadence = _adaptive_effect_window(
        engine,
        now=now,
        direction=direction,
        error=error,
        tolerance=settings["tolerance"],
        max_window_sec=settings["effect_window_sec"],
    )
    if not direction_changed:
        _append_sample(engine, now, vpd, cadence["interval_sec"])

    if direction is None:
        # Sobald der reale Messwert das VPD-Zielband erreicht, wird ein noch
        # höherer Sollwert der vorherigen Heizstufe sofort verworfen. Damit
        # heizt AUTO nicht bis zum alten Stufenziel weiter und überschwingt.
        engine["temp_target"] = _clip(
            temp,
            settings["temp_min"],
            settings["temp_max"],
        )

    elapsed = max(0.0, now - float(engine.get("stage_started_at") or now))
    improvement = _stage_effect(engine, direction) if direction else 0.0

    if direction and elapsed >= cadence["interval_sec"]:
        # Das nächste Fenster wird nach der Entscheidung frisch gewählt. Eine
        # neue Aktorstufe erzwingt dabei über _set_stage wieder 60 Sekunden;
        # eine unveränderte, träge Stufe kann auf 120 Sekunden wechseln.
        engine.pop("_cadence_window_sec", None)
        engine.pop("_cadence_phase", None)
        if direction == "raise":
            _advance_raise_stage(
                rt,
                engine,
                now=now,
                vpd=vpd,
                temp=temp,
                improvement=improvement,
                settings=regulation_settings,
                availability=raise_availability,
                outside_drying=outside_drying,
            )
        else:
            _advance_lower_stage(
                engine,
                now=now,
                vpd=vpd,
                improvement=improvement,
                settings=regulation_settings,
                availability=availability,
                outside_humidifying=outside_humidifying,
                preferred_temp=preferred_temp,
            )
        cadence = _adaptive_effect_window(
            engine,
            now=now,
            direction=direction,
            error=error,
            tolerance=settings["tolerance"],
            max_window_sec=settings["effect_window_sec"],
        )
        elapsed = max(
            0.0,
            now - float(engine.get("stage_started_at") or now),
        )
        improvement = 0.0

    engine["last_temp"] = temp

    stage = engine.get("stage") or "in_band"
    effective_target = _clip(
        engine.get("temp_target", base_target),
        settings["temp_min"],
        settings["temp_max"],
    )

    # Klassische Temperatur-Regeltoleranzen gehören nicht zur intelligenten
    # VPD-Strategie. Eine kleine interne Hysterese verhindert Relaisflattern,
    # ohne einen freigegebenen VPD-Temperaturschritt zu verschlucken.
    vpd_temp_hysteresis = min(
        0.25,
        max(0.10, float(settings["temp_step"]) * 0.40),
    )

    actions = {
        "fan": _fan_idle_action(rt),
        "heating": _thermostat_action(
            rt,
            temp=temp,
            target=effective_target,
            tolerance=vpd_temp_hysteresis,
            temp_min=settings["temp_min"],
            temp_max=settings["temp_max"],
            reason=f"(VPD Temperaturziel {effective_target:.1f}°C)",
        ),
        "humidifier": _off_action(rt, "humidifier", "(VPD keine Befeuchtung)"),
        "dehumidifier": _off_action(rt, "dehumidifier", "(VPD keine Entfeuchtung)"),
    }

    hold_exhaust_limit = bool(
        direction == "raise"
        and stage == "limited"
        and engine.get("fan_sweep_complete")
    )
    if (
        stage in {"exhaust", "heat", "dehumidify"}
        or hold_exhaust_limit
    ) and availability["fan"] and outside_drying:
        actions["fan"] = _fan_regulation_action(
            rt,
            engine.get("fan_level"),
            (
                "(VPD Abluft-Maximum halten)"
                if hold_exhaust_limit
                else "(VPD Außenluft trockener)"
            ),
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

    # Harte Feuchtegrenzen dürfen niemals durch einen gegensinnigen Aktorplan
    # verletzt werden. Insbesondere wird bei Feuchte über Maximum nicht
    # befeuchtet und bei bereits passendem/zu hohem VPD nicht weiter geheizt.
    if hum >= settings["hum_max"]:
        actions["humidifier"] = _off_action(
            rt,
            "humidifier",
            "(VPD Feuchte-Obergrenze)",
        )
    if hum <= settings["hum_min"]:
        actions["dehumidifier"] = _off_action(
            rt,
            "dehumidifier",
            "(VPD Feuchte-Untergrenze)",
        )
    if humidity_too_high and not low_needed:
        actions["heating"] = _off_action(
            rt,
            "heating",
            "(VPD Feuchte-Obergrenze · Heizung pausiert)",
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

    setpoints = _coupled_setpoints(
        settings,
        target_curve,
        effective_target,
    )
    engine["hum_target"] = setpoints["hum"]

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
        settings=regulation_settings,
        availability=(
            raise_availability
            if direction == "raise"
            else availability
        ),
        outside_drying=outside_drying,
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
        "effective_vpd_target": round(setpoints["vpd"], 3),
        "tolerance": settings["tolerance"],
        "error": round(error, 3),
        "base_temp_target": round(base_target, 2),
        "preferred_temp_target": round(preferred_temp, 2),
        "effective_temp_target": round(effective_target, 2),
        "effective_hum_target": round(setpoints["hum"], 2),
        "setpoints": {
            "vpd": round(setpoints["vpd"], 3),
            "temp": round(setpoints["temp"], 2),
            "hum": round(setpoints["hum"], 2),
            "calculated_hum": round(setpoints["calculated_hum"], 2),
            "hum_band_min": round(setpoints["hum_band_min"], 2),
            "hum_band_max": round(setpoints["hum_band_max"], 2),
            "calculated_hum_band_min": round(
                setpoints["calculated_hum_band_min"],
                2,
            ),
            "calculated_hum_band_max": round(
                setpoints["calculated_hum_band_max"],
                2,
            ),
            "curve_temp_min": round(setpoints["curve_temp_min"], 2),
            "curve_temp_max": round(setpoints["curve_temp_max"], 2),
            "at_temp_max": {
                "temp": round(setpoints["at_temp_max"]["temp"], 2),
                "hum": round(setpoints["at_temp_max"]["hum"], 2),
                "calculated_hum": round(
                    setpoints["at_temp_max"]["calculated_hum"],
                    2,
                ),
                "within_humidity_range": bool(
                    setpoints["at_temp_max"]["within_humidity_range"]
                ),
            },
            "within_humidity_range": bool(
                setpoints["within_humidity_range"]
            ),
            "constrained": bool(setpoints["constrained"]),
            "explanation": setpoints["explanation"],
        },
        "ramp": deepcopy(ramp),
        "range": {
            "temp_min": settings["temp_min"],
            "temp_max": settings["temp_max"],
            "hum_min": settings["hum_min"],
            "hum_max": settings["hum_max"],
        },
        "humidity_limit": {
            "hard": True,
            "too_low": humidity_too_low,
            "too_high": humidity_too_high,
            "minimum": settings["hum_min"],
            "maximum": settings["hum_max"],
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
            "window_sec": cadence["interval_sec"],
            "max_window_sec": cadence["max_interval_sec"],
            "cadence": deepcopy(cadence),
            "elapsed_sec": round(elapsed, 1),
            "improvement_kpa": round(improvement, 3),
            "last_improvement_kpa": (
                round(float(engine["last_evaluation_improvement"]), 3)
                if engine.get("last_evaluation_improvement") is not None
                else None
            ),
            "minimum_kpa": settings["min_effect"],
            "next_evaluation_sec": max(
                0,
                int(round(cadence["interval_sec"] - elapsed)),
            ) if direction and stage != "in_band" else None,
        },
        "fan_level": engine.get("fan_level"),
        "strategy_progress": {
            "fan": {
                "level": engine.get("fan_level"),
                "minimum": engine.get("fan_min"),
                "maximum": engine.get("fan_max"),
                "complete": bool(engine.get("fan_sweep_complete")),
            },
            "temperature": {
                "measured": round(temp, 2),
                "target": round(effective_target, 2),
                "minimum": settings["temp_min"],
                "maximum": settings["temp_max"],
                "allowed_minimum": settings["temp_min"],
                "allowed_maximum": settings["temp_max"],
                "preferred_curve_minimum": round(target_curve["temp_min"], 2),
                "preferred_curve_maximum": round(target_curve["temp_max"], 2),
                "hysteresis": round(vpd_temp_hysteresis, 2),
                "complete": bool(engine.get("heat_sweep_complete")),
                "stall_windows": int(engine.get("heat_stall_windows") or 0),
            },
        },
        "managed_devices": managed_devices,
        "unavailable_devices": [
            device for device in VPD_MANAGED_DEVICES if not availability[device]
        ],
        "actions": deepcopy(actions),
        # Ausschließlich ein begrenzter, öffentlicher Entscheidungsverlauf.
        # Interne Samples und Zustandsmaschinen-Caches verlassen den Runtime-
        # Prozess weiterhin nicht.
        "events": deepcopy(list(engine.get("events") or [])[-20:]),
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
            st.live_state["vpd_hum_target"] = setpoints["hum"]
            st.live_state["vpd_effective_target"] = setpoints["vpd"]
            if takeover:
                st.live_state["temp_target"] = effective_target
                st.live_state["hum_target"] = setpoints["hum"]

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
