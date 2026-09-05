"""Pure VPD-Konfiguration und flüchtiger Runtime-Reset.

Dieses Modul importiert absichtlich keine Aktor-/Netzwerkpfade. Profil- und
Konfigurationsvalidierung bleiben dadurch auch in Offline-Tools und Tests leicht
verwendbar.
"""

from __future__ import annotations

from copy import deepcopy
import math

from core.config import migrate_vpd_phase_config
from core.helpers import calculate_vpd, minutes_now
from core.runtime import resolve_runtime


VPD_CONTROL_MODES = {"OFF", "MONITOR", "AUTO"}
VPD_SECONDARY_PRIORITIES = {"HUMIDITY", "TEMPERATURE"}
VPD_MANAGED_DEVICES = ("fan", "heating", "humidifier", "dehumidifier")
VPD_ENGINE_KEY = "_vpd_control_engine"
VPD_GENERATION_KEY = "_vpd_control_generation"
VPD_PUBLIC_KEY = "vpd_control"

_RAMPED_PHASE_KEYS = (
    "target",
    "tolerance",
    "temp_min",
    "temp_max",
    "hum_min",
    "hum_max",
)


def _finite(cfg, key):
    try:
        value = float(cfg[key])
    except KeyError as exc:
        raise ValueError(f"{key} fehlt") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} muss numerisch sein") from exc

    if not math.isfinite(value):
        raise ValueError(f"{key} muss endlich sein")
    return value


def _bounded(cfg, key, minimum, maximum):
    value = _finite(cfg, key)
    if value < minimum or value > maximum:
        raise ValueError(
            f"{key} muss zwischen {minimum:g} und {maximum:g} liegen"
        )
    return value


def validate_vpd_config(cfg):
    """Validiert beide VPD-Phasen einschließlich Erreichbarkeit."""

    effective = dict(cfg or {})
    migrate_vpd_phase_config(effective)

    mode = str(effective.get("VPD_CONTROL_MODE", "OFF") or "OFF").upper()
    if mode not in VPD_CONTROL_MODES:
        raise ValueError("VPD_CONTROL_MODE muss OFF, MONITOR oder AUTO sein")

    phases = {}
    for profile, suffix, label in (
        ("TAG", "DAY", "Tag"),
        ("NACHT", "NIGHT", "Nacht"),
    ):
        target_key = f"VPD_TARGET_{suffix}"
        tolerance_key = f"VPD_TOLERANCE_{suffix}"
        temp_min_key = f"VPD_TEMP_MIN_{suffix}"
        temp_max_key = f"VPD_TEMP_MAX_{suffix}"
        hum_min_key = f"VPD_HUM_MIN_{suffix}"
        hum_max_key = f"VPD_HUM_MAX_{suffix}"
        priority_key = f"VPD_SECONDARY_PRIORITY_{suffix}"

        target = _bounded(effective, target_key, 0.1, 3.5)
        tolerance = _bounded(effective, tolerance_key, 0.01, 0.5)
        temp_min = _bounded(effective, temp_min_key, -10.0, 50.0)
        temp_max = _bounded(effective, temp_max_key, -10.0, 50.0)
        hum_min = _bounded(effective, hum_min_key, 1.0, 99.0)
        hum_max = _bounded(effective, hum_max_key, 1.0, 99.0)
        secondary_priority = str(
            effective.get(priority_key, "HUMIDITY") or "HUMIDITY"
        ).strip().upper()
        if secondary_priority not in VPD_SECONDARY_PRIORITIES:
            raise ValueError(
                f"{priority_key} muss HUMIDITY oder TEMPERATURE sein"
            )

        if temp_min >= temp_max:
            raise ValueError(
                f"{temp_min_key} muss kleiner als {temp_max_key} sein"
            )
        if hum_min >= hum_max:
            raise ValueError(
                f"{hum_min_key} muss kleiner als {hum_max_key} sein"
            )

        attainable_min = float(calculate_vpd(temp_min, hum_max))
        attainable_max = float(calculate_vpd(temp_max, hum_min))
        if target + tolerance < attainable_min or target - tolerance > attainable_max:
            raise ValueError(
                f"{target_key} ist im VPD-Fenster für {label} nicht "
                f"erreichbar ({attainable_min:.2f} bis "
                f"{attainable_max:.2f} kPa)"
            )

        phases[profile] = {
            "name": profile,
            "label": label,
            "target": target,
            "tolerance": tolerance,
            "temp_min": temp_min,
            "temp_max": temp_max,
            "hum_min": hum_min,
            "hum_max": hum_max,
            "secondary_priority": secondary_priority,
            "attainable_min": attainable_min,
            "attainable_max": attainable_max,
        }

    effect_window = _bounded(effective, "VPD_EFFECT_WINDOW_MIN", 1, 30)
    if not effect_window.is_integer():
        raise ValueError("VPD_EFFECT_WINDOW_MIN muss eine ganze Minute sein")

    min_effect = _bounded(effective, "VPD_MIN_EFFECT_KPA", 0.005, 0.5)
    temp_step = _bounded(effective, "VPD_TEMP_STEP", 0.1, 2.0)
    fan_step = _bounded(effective, "VPD_FAN_STEP", 1, 25)
    if not fan_step.is_integer():
        raise ValueError("VPD_FAN_STEP muss ganzzahlig sein")

    return {
        "mode": mode,
        "target_day": phases["TAG"]["target"],
        "target_night": phases["NACHT"]["target"],
        "tolerance_day": phases["TAG"]["tolerance"],
        "tolerance_night": phases["NACHT"]["tolerance"],
        "phases": phases,
        "effect_window_sec": int(effect_window * 60),
        "min_effect": min_effect,
        "temp_step": temp_step,
        "fan_step": int(fan_step),
        # Aggregierte Werte bleiben für Diagnose-Clients aus 3.16.0 erhalten;
        # die Regelung selbst verwendet ausschließlich das aktive Phasenobjekt.
        "attainable_min": min(
            phase["attainable_min"] for phase in phases.values()
        ),
        "attainable_max": max(
            phase["attainable_max"] for phase in phases.values()
        ),
    }


def validate_vpd_environment_alignment(cfg):
    """Stellt sicher, dass aktive VPD-Modi harte Stationsgrenzen einhalten."""

    settings = validate_vpd_config(cfg)
    # Im ausgeschalteten Modus sind die VPD-Werte nur eine gespeicherte
    # Vorbereitung. Sie dürfen deshalb keine ansonsten unabhängige Änderung an
    # Klima oder Grenzwerten blockieren. Beim Wechsel auf MONITOR/AUTO wird die
    # Übereinstimmung im selben Speichervorgang zwingend geprüft.
    if settings["mode"] == "OFF":
        return settings

    min_temp = _finite(cfg, "MIN_TEMP")
    max_temp = _finite(cfg, "MAX_TEMP")
    min_hum = _finite(cfg, "MIN_HUM")
    max_hum = _finite(cfg, "MAX_HUM")

    for phase in settings["phases"].values():
        if phase["temp_min"] < min_temp or phase["temp_max"] > max_temp:
            raise ValueError(
                f"Das VPD-Temperaturfenster für {phase['label']} muss "
                "innerhalb MIN_TEMP/MAX_TEMP liegen"
            )
        if phase["hum_min"] < min_hum or phase["hum_max"] > max_hum:
            raise ValueError(
                f"Das VPD-Feuchtefenster für {phase['label']} muss "
                "innerhalb MIN_HUM/MAX_HUM liegen"
            )
    return settings


def _forward_progress(now_min, start_min, duration_min):
    """Fortschritt eines vorwärts laufenden Tageszeitfensters oder ``None``."""

    if duration_min <= 0:
        return None

    elapsed = (float(now_min) - float(start_min)) % 1440.0
    if elapsed >= float(duration_min):
        return None
    return max(0.0, min(1.0, elapsed / float(duration_min)))


def _interpolate_phase(source, destination, progress):
    effective = {
        key: float(source[key])
        + (float(destination[key]) - float(source[key])) * float(progress)
        for key in _RAMPED_PHASE_KEYS
    }
    effective["attainable_min"] = float(
        calculate_vpd(effective["temp_min"], effective["hum_max"])
    )
    effective["attainable_max"] = float(
        calculate_vpd(effective["temp_max"], effective["hum_min"])
    )
    # Eine Priorität ist kategorial und kann nicht mathematisch interpoliert
    # werden. Bis zur Rampenmitte gilt die Ausgangs-, danach die Zielphase.
    effective["secondary_priority"] = (
        destination["secondary_priority"]
        if float(progress) >= 0.5
        else source["secondary_priority"]
    )
    return effective


def calculate_vpd_schedule(settings, cfg, profile, *, now_min=None):
    """Berechnet das geglättete VPD-Ziel samt erlaubtem Klimafenster.

    Die vorhandene Rampendauer bleibt die gemeinsame Profilvorgabe. Im
    intelligenten Modus interpoliert sie jedoch VPD-Ziel, Toleranz und
    Betriebsfenster statt eines festen Temperatur-Sollwerts. Die Funktion ist
    rein und verändert weder Runtime- noch Aktorzustand. Ihre Zeitfenster sind
    ausschließlich an DAY_START_MIN/NIGHT_START_MIN gebunden; LIGHT_SUN_*, ein
    Lichtcontroller oder ein Helligkeitssensor sind ausdrücklich keine
    Voraussetzung.
    """

    phases = settings.get("phases") or {}
    normalized_profile = "NACHT" if str(profile).upper() == "NACHT" else "TAG"
    day = dict(phases.get("TAG") or {})
    night = dict(phases.get("NACHT") or {})
    if not day or not night:
        raise ValueError("VPD-Phasenkonfiguration für Tag/Nacht fehlt")

    duration = max(0, min(1440, int(cfg.get("RAMP_DURATION_MIN", 0) or 0)))
    enabled = bool(cfg.get("RAMP_ENABLED", 0)) and duration > 0
    current_minute = minutes_now() if now_min is None else float(now_min) % 1440.0
    day_start = int(cfg.get("DAY_START_MIN", 0)) % 1440
    night_start = int(cfg.get("NIGHT_START_MIN", 0)) % 1440

    transition = None
    progress = None
    source = None
    destination = None
    start_min = None
    end_min = None

    if enabled:
        morning_progress = _forward_progress(
            current_minute,
            day_start,
            duration,
        )
        evening_start = (night_start - duration) % 1440
        evening_progress = _forward_progress(
            current_minute,
            evening_start,
            duration,
        )

        if morning_progress is not None:
            transition = "morning"
            progress = morning_progress
            source, destination = night, day
            start_min = day_start
            end_min = (day_start + duration) % 1440
        elif evening_progress is not None:
            transition = "evening"
            progress = evening_progress
            source, destination = day, night
            start_min = evening_start
            end_min = night_start

    if transition is None:
        effective = dict(phases[normalized_profile])
        schedule_key = f"steady:{normalized_profile}"
        start_target = end_target = float(effective["target"])
        progress_value = 1.0
    else:
        effective = _interpolate_phase(source, destination, progress)
        schedule_key = f"ramp:{transition}"
        start_target = float(source["target"])
        end_target = float(destination["target"])
        progress_value = float(progress)

    effective["name"] = normalized_profile
    effective["label"] = "Nacht" if normalized_profile == "NACHT" else "Tag"

    ramp = {
        "enabled": enabled,
        "active": transition is not None,
        "kind": transition,
        "key": schedule_key,
        "duration_min": duration,
        "progress": progress_value,
        "start_min": start_min,
        "end_min": end_min,
        "start_target": start_target,
        "end_target": end_target,
        "target": float(effective["target"]),
    }
    return effective, ramp


def reset_vpd_control(runtime=None, *, reason="zurückgesetzt"):
    """Setzt ausschließlich den flüchtigen VPD-Lern-/Stufenzustand zurück."""

    rt = resolve_runtime(runtime)
    with rt.state_lock:
        generation = rt.state.live_state.get(VPD_GENERATION_KEY, 0)
        try:
            generation = int(generation)
        except (TypeError, ValueError):
            generation = 0
        rt.state.live_state[VPD_GENERATION_KEY] = generation + 1
        rt.state.live_state.pop(VPD_ENGINE_KEY, None)
        climate_target = rt.state.live_state.get("climate_temp_target")
        try:
            climate_target = float(climate_target)
        except (TypeError, ValueError):
            climate_target = None
        if climate_target is not None and math.isfinite(climate_target):
            rt.state.live_state["temp_target"] = climate_target
        climate_hum_target = rt.state.live_state.get("climate_hum_target")
        try:
            climate_hum_target = float(climate_hum_target)
        except (TypeError, ValueError):
            climate_hum_target = None
        if climate_hum_target is not None and math.isfinite(climate_hum_target):
            rt.state.live_state["hum_target"] = climate_hum_target
        climate_hum_tol = rt.state.live_state.get("climate_hum_tol")
        try:
            climate_hum_tol = float(climate_hum_tol)
        except (TypeError, ValueError):
            climate_hum_tol = None
        if climate_hum_tol is not None and math.isfinite(climate_hum_tol):
            rt.state.live_state["hum_tol"] = climate_hum_tol
        rt.state.live_state.pop("vpd_temp_target", None)
        rt.state.live_state.pop("vpd_base_temp_target", None)
        rt.state.live_state.pop("vpd_hum_target", None)
        rt.state.live_state.pop("vpd_effective_target", None)
        rt.state.live_state[VPD_PUBLIC_KEY] = {
            "mode": str(rt.config.get("VPD_CONTROL_MODE", "OFF") or "OFF").upper(),
            "active": False,
            "takeover": False,
            "ready": False,
            "stage": "reset",
            "reason": reason,
            "managed_devices": [],
            "actions": {},
        }


def vpd_device_context(device, runtime=None):
    """Liefert die verbindliche AUTO-Zuordnung für eine Geräteoberfläche.

    Die Konfiguration ist für die Sperrentscheidung maßgeblich. Dadurch bleibt
    ein ENV-Gerät auch während eines Sensor-Fallbacks gesperrt und kann nicht
    unbemerkt verändert werden, kurz bevor AUTO die Übernahme fortsetzt.
    """

    rt = resolve_runtime(runtime)

    # Lazy Import hält die reine VPD-Konfiguration frei von einem Modulzyklus
    # über core.devices -> core.runtime -> core.config.
    from core.devices import get_device_mode, validate_device_name

    validate_device_name(device)
    configured_mode = str(
        rt.config.get("VPD_CONTROL_MODE", "OFF") or "OFF"
    ).upper()
    device_mode = get_device_mode(device, runtime=rt)
    supported = device in VPD_MANAGED_DEVICES
    automatic = configured_mode == "AUTO"
    participating = bool(
        supported
        and automatic
        and device_mode == "ENV"
    )

    with rt.state_lock:
        public = deepcopy(rt.state.live_state.get(VPD_PUBLIC_KEY) or {})

    public_mode = str(public.get("mode") or configured_mode).upper()
    ready = bool(
        public_mode == "AUTO"
        and public.get("takeover")
        and public.get("ready")
    )
    managed = bool(
        participating
        and ready
        and device in (public.get("managed_devices") or [])
    )
    action = (public.get("actions") or {}).get(device)
    if not isinstance(action, dict) or not participating:
        action = None

    if managed:
        status = "controlled"
    elif participating:
        status = "waiting"
    elif supported and automatic:
        status = "available"
    elif supported:
        status = "inactive"
    else:
        status = "not_supported"

    action_reason = action.get("reason") if isinstance(action, dict) else None
    return {
        "supported": supported,
        "automatic": automatic,
        "participating": participating,
        "managed": managed,
        # Ein AUTO/ENV-Gerät bleibt auch im sicheren Fallback gesperrt.
        "locked": participating,
        "status": status,
        "mode": configured_mode,
        "ready": ready,
        "fallback": bool(public.get("fallback")) if participating else False,
        "stage": public.get("stage") if participating else None,
        "stage_label": public.get("stage_label") if participating else None,
        "reason": action_reason or (
            public.get("reason") if participating else None
        ),
        "action": deepcopy(action),
    }


__all__ = (
    "VPD_CONTROL_MODES",
    "VPD_SECONDARY_PRIORITIES",
    "VPD_ENGINE_KEY",
    "VPD_GENERATION_KEY",
    "VPD_MANAGED_DEVICES",
    "VPD_PUBLIC_KEY",
    "calculate_vpd_schedule",
    "reset_vpd_control",
    "vpd_device_context",
    "validate_vpd_config",
    "validate_vpd_environment_alignment",
)
