"""Pure VPD-Konfiguration und flüchtiger Runtime-Reset.

Dieses Modul importiert absichtlich keine Aktor-/Netzwerkpfade. Profil- und
Konfigurationsvalidierung bleiben dadurch auch in Offline-Tools und Tests leicht
verwendbar.
"""

from __future__ import annotations

import math

from core.config import migrate_vpd_phase_config
from core.helpers import calculate_vpd
from core.runtime import resolve_runtime


VPD_CONTROL_MODES = {"OFF", "MONITOR", "AUTO"}
VPD_MANAGED_DEVICES = ("fan", "heating", "humidifier", "dehumidifier")
VPD_ENGINE_KEY = "_vpd_control_engine"
VPD_GENERATION_KEY = "_vpd_control_generation"
VPD_PUBLIC_KEY = "vpd_control"


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

        target = _bounded(effective, target_key, 0.1, 3.5)
        tolerance = _bounded(effective, tolerance_key, 0.01, 0.5)
        temp_min = _bounded(effective, temp_min_key, -10.0, 50.0)
        temp_max = _bounded(effective, temp_max_key, -10.0, 50.0)
        hum_min = _bounded(effective, hum_min_key, 1.0, 99.0)
        hum_max = _bounded(effective, hum_max_key, 1.0, 99.0)

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
        rt.state.live_state.pop("vpd_temp_target", None)
        rt.state.live_state.pop("vpd_base_temp_target", None)
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


__all__ = (
    "VPD_CONTROL_MODES",
    "VPD_ENGINE_KEY",
    "VPD_GENERATION_KEY",
    "VPD_MANAGED_DEVICES",
    "VPD_PUBLIC_KEY",
    "reset_vpd_control",
    "validate_vpd_config",
    "validate_vpd_environment_alignment",
)
