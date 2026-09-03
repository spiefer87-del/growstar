# core/profile.py

import os
import json
from copy import deepcopy
import math
from pathlib import Path
import tempfile
import threading

from core.config import (
    DEFAULT_CONFIG,
    VPD_LEGACY_SHARED_KEYS,
    migrate_vpd_phase_config,
)
from core.runtime import resolve_runtime
from core.tents import DEFAULT_TENT_ID
from core.helpers import (
    calculate_vpd,
    minutes_now,
    is_night,
)


def get_profile(runtime=None):
    rt = resolve_runtime(runtime)
    cfg = rt.config
    st = rt.state

    now_min = minutes_now()

    day_start = int(cfg["DAY_START_MIN"])
    night_start = int(cfg["NIGHT_START_MIN"])

    if is_night(now_min, night_start, day_start):
        profile = "NACHT"
    else:
        profile = "TAG"

    if profile != st.current_profile:
        print(
            f"🔄 [{rt.tent_id}] Profilwechsel: "
            f"{st.current_profile} -> {profile} "
            f"({minutes_now()} min)"
        )
        st.current_profile = profile

    st.live_state["profile"] = profile

    return profile


PROFILE_FILE = "profiles.json"

VPD_PROFILE_SETTING_KEYS = (
    "VPD_TARGET_DAY",
    "VPD_TOLERANCE_DAY",
    "VPD_TEMP_MIN_DAY",
    "VPD_TEMP_MAX_DAY",
    "VPD_HUM_MIN_DAY",
    "VPD_HUM_MAX_DAY",
    "VPD_TARGET_NIGHT",
    "VPD_TOLERANCE_NIGHT",
    "VPD_TEMP_MIN_NIGHT",
    "VPD_TEMP_MAX_NIGHT",
    "VPD_HUM_MIN_NIGHT",
    "VPD_HUM_MAX_NIGHT",
)


PROFILE_SETTING_KEYS = (
    "DAY_TEMP",
    "NIGHT_TEMP",
    "DAY_HUM",
    "NIGHT_HUM",
    "DAY_TEMP_TOL",
    "NIGHT_TEMP_TOL",
    "DAY_HUM_TOL",
    "NIGHT_HUM_TOL",
    "DAY_START_MIN",
    "NIGHT_START_MIN",
    "RAMP_ENABLED",
    "RAMP_DURATION_MIN",
    "LIGHT_SUN_ENABLED",
    "LIGHT_SUNRISE_DURATION_MIN",
    "LIGHT_SUNSET_DURATION_MIN",
    "LIGHT_SUN_MIN_LEVEL",
    *VPD_PROFILE_SETTING_KEYS,
)

PROFILE_COMPATIBILITY_DEFAULTS = {
    key: deepcopy(DEFAULT_CONFIG[key])
    for key in (
        "LIGHT_SUN_ENABLED",
        "LIGHT_SUNRISE_DURATION_MIN",
        "LIGHT_SUNSET_DURATION_MIN",
        "LIGHT_SUN_MIN_LEVEL",
    )
}


def _profile_compatibility_values(settings):
    """Ergänzt alte Vorlagen ohne ihre bisherige Klimawirkung zu verändern.

    VPD-Ziele werden aus den vorhandenen Tag-/Nacht-Sollwerten berechnet. Das
    neue Betriebsfenster umschließt die vorhandenen Sollwerte samt Toleranzen.
    Dadurch wird ein altes Profil beim ersten Laden nicht heimlich auf generische
    VPD-Werte umgestellt.
    """

    values = deepcopy(PROFILE_COMPATIBILITY_DEFAULTS)
    source = deepcopy(settings) if isinstance(settings, dict) else {}
    migrate_vpd_phase_config(source, remove_legacy=True)

    derived = {
        key: deepcopy(DEFAULT_CONFIG[key])
        for key in VPD_PROFILE_SETTING_KEYS
    }

    try:
        for suffix in ("DAY", "NIGHT"):
            temp = float(settings[f"{suffix}_TEMP"])
            hum = float(settings[f"{suffix}_HUM"])
            temp_tol = abs(float(settings[f"{suffix}_TEMP_TOL"]))
            hum_tol = abs(float(settings[f"{suffix}_HUM_TOL"]))

            temp_min = temp - temp_tol
            temp_max = temp + temp_tol
            hum_min = max(1.0, hum - hum_tol)
            hum_max = min(99.0, hum + hum_tol)

            if temp_max - temp_min < 0.2:
                temp_min -= 0.1
                temp_max += 0.1
            if hum_max - hum_min < 1.0:
                hum_min = max(1.0, hum_min - 0.5)
                hum_max = min(99.0, hum_max + 0.5)

            derived.update({
                f"VPD_TARGET_{suffix}": round(
                    float(calculate_vpd(temp, hum)),
                    2,
                ),
                f"VPD_TOLERANCE_{suffix}": float(
                    DEFAULT_CONFIG[f"VPD_TOLERANCE_{suffix}"]
                ),
                f"VPD_TEMP_MIN_{suffix}": round(temp_min, 2),
                f"VPD_TEMP_MAX_{suffix}": round(temp_max, 2),
                f"VPD_HUM_MIN_{suffix}": round(hum_min, 2),
                f"VPD_HUM_MAX_{suffix}": round(hum_max, 2),
            })
    except (KeyError, TypeError, ValueError, OverflowError):
        pass

    for key in VPD_PROFILE_SETTING_KEYS:
        values[key] = deepcopy(source.get(key, derived[key]))

    return values

_PROFILE_LOCK = threading.RLock()


class ProfileActivationError(ValueError):
    """Ein vorhandenes Profil ist mit der Zielstation nicht sicher nutzbar."""

    def __init__(self, code, message):
        self.code = str(code)
        super().__init__(message)


def _finite_number(data, key):
    try:
        value = float(data[key])
    except KeyError as exc:
        raise ValueError(f"{key} fehlt") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} muss numerisch sein") from exc

    if not math.isfinite(value):
        raise ValueError(f"{key} muss endlich sein")

    return value


def _bounded(value, key, minimum, maximum):
    if value < minimum or value > maximum:
        raise ValueError(
            f"{key} muss zwischen {minimum:g} und {maximum:g} liegen"
        )
    return value


def normalize_profile_settings(data):
    """Validiert eine vollständige, noch nicht aktivierte Profilvorlage."""

    if not isinstance(data, dict):
        raise TypeError("Profil muss ein JSON-Objekt sein")

    # Alte API-Clients und vorhandene Tests dürfen weiterhin ein Profil ohne
    # die später ergänzten Sonnen-/VPD-Felder senden. Die fehlenden VPD-Werte
    # werden aus genau diesem Profil abgeleitet, nicht aus einem fremden Preset.
    data = deepcopy(data)
    compatibility = _profile_compatibility_values(data)
    migrate_vpd_phase_config(data, remove_legacy=True)
    for key, default in compatibility.items():
        data.setdefault(key, deepcopy(default))

    unknown = sorted(set(data) - set(PROFILE_SETTING_KEYS))
    if unknown:
        raise ValueError(
            "Unbekannte Profileinstellungen: " + ", ".join(unknown)
        )

    missing = [key for key in PROFILE_SETTING_KEYS if key not in data]
    if missing:
        raise ValueError(
            "Fehlende Profileinstellungen: " + ", ".join(missing)
        )

    result = {
        "DAY_TEMP": _bounded(
            _finite_number(data, "DAY_TEMP"),
            "DAY_TEMP",
            -20,
            60,
        ),
        "NIGHT_TEMP": _bounded(
            _finite_number(data, "NIGHT_TEMP"),
            "NIGHT_TEMP",
            -20,
            60,
        ),
        "DAY_HUM": _bounded(
            _finite_number(data, "DAY_HUM"),
            "DAY_HUM",
            0,
            100,
        ),
        "NIGHT_HUM": _bounded(
            _finite_number(data, "NIGHT_HUM"),
            "NIGHT_HUM",
            0,
            100,
        ),
        "DAY_TEMP_TOL": _bounded(
            _finite_number(data, "DAY_TEMP_TOL"),
            "DAY_TEMP_TOL",
            0,
            10,
        ),
        "NIGHT_TEMP_TOL": _bounded(
            _finite_number(data, "NIGHT_TEMP_TOL"),
            "NIGHT_TEMP_TOL",
            0,
            10,
        ),
        "DAY_HUM_TOL": _bounded(
            _finite_number(data, "DAY_HUM_TOL"),
            "DAY_HUM_TOL",
            0,
            30,
        ),
        "NIGHT_HUM_TOL": _bounded(
            _finite_number(data, "NIGHT_HUM_TOL"),
            "NIGHT_HUM_TOL",
            0,
            30,
        ),
    }

    for key in ("DAY_START_MIN", "NIGHT_START_MIN"):
        value = _finite_number(data, key)
        if not value.is_integer():
            raise ValueError(f"{key} muss eine ganze Minute sein")
        result[key] = int(_bounded(value, key, 0, 1439))

    ramp_enabled = _finite_number(data, "RAMP_ENABLED")
    if not ramp_enabled.is_integer() or int(ramp_enabled) not in {0, 1}:
        raise ValueError("RAMP_ENABLED muss 0 oder 1 sein")
    result["RAMP_ENABLED"] = int(ramp_enabled)

    ramp_duration = _finite_number(data, "RAMP_DURATION_MIN")
    if not ramp_duration.is_integer():
        raise ValueError("RAMP_DURATION_MIN muss eine ganze Minute sein")
    result["RAMP_DURATION_MIN"] = int(
        _bounded(ramp_duration, "RAMP_DURATION_MIN", 0, 240)
    )

    if result["RAMP_ENABLED"] and result["RAMP_DURATION_MIN"] < 5:
        raise ValueError(
            "RAMP_DURATION_MIN muss bei aktiver Rampe mindestens 5 sein"
        )

    light_sun_enabled = _finite_number(data, "LIGHT_SUN_ENABLED")
    if (
        not light_sun_enabled.is_integer()
        or int(light_sun_enabled) not in {0, 1}
    ):
        raise ValueError("LIGHT_SUN_ENABLED muss 0 oder 1 sein")
    result["LIGHT_SUN_ENABLED"] = int(light_sun_enabled)

    for key in (
        "LIGHT_SUNRISE_DURATION_MIN",
        "LIGHT_SUNSET_DURATION_MIN",
    ):
        value = _finite_number(data, key)
        if not value.is_integer():
            raise ValueError(f"{key} muss eine ganze Minute sein")
        result[key] = int(_bounded(value, key, 0, 240))

    light_sun_min_level = _finite_number(data, "LIGHT_SUN_MIN_LEVEL")
    if not light_sun_min_level.is_integer():
        raise ValueError("LIGHT_SUN_MIN_LEVEL muss eine ganze Prozentzahl sein")
    result["LIGHT_SUN_MIN_LEVEL"] = int(
        _bounded(light_sun_min_level, "LIGHT_SUN_MIN_LEVEL", 11, 100)
    )

    for suffix in ("DAY", "NIGHT"):
        target_key = f"VPD_TARGET_{suffix}"
        tolerance_key = f"VPD_TOLERANCE_{suffix}"
        temp_min_key = f"VPD_TEMP_MIN_{suffix}"
        temp_max_key = f"VPD_TEMP_MAX_{suffix}"
        hum_min_key = f"VPD_HUM_MIN_{suffix}"
        hum_max_key = f"VPD_HUM_MAX_{suffix}"

        result.update({
            target_key: _bounded(
                _finite_number(data, target_key), target_key, 0.1, 3.5
            ),
            tolerance_key: _bounded(
                _finite_number(data, tolerance_key), tolerance_key, 0.01, 0.5
            ),
            temp_min_key: _bounded(
                _finite_number(data, temp_min_key), temp_min_key, -10, 50
            ),
            temp_max_key: _bounded(
                _finite_number(data, temp_max_key), temp_max_key, -10, 50
            ),
            hum_min_key: _bounded(
                _finite_number(data, hum_min_key), hum_min_key, 1, 99
            ),
            hum_max_key: _bounded(
                _finite_number(data, hum_max_key), hum_max_key, 1, 99
            ),
        })

    # Dieselbe Erreichbarkeitsprüfung wie bei einer Stationskonfiguration.
    from core.vpd import validate_vpd_config

    validation_cfg = deepcopy(DEFAULT_CONFIG)
    validation_cfg.update(result)
    validate_vpd_config(validation_cfg)

    return result


def get_active_profile(runtime=None):
    """Aktives Preset pro Runtime.

    Alte Installationen von tent_1 kennen ACTIVE_PROFILE noch nicht in der
    config.json. Dort bleibt profiles.json als Fallback erhalten. Zusätzliche
    Stationen verwenden dagegen ausschließlich ihren eigenen Config-Wert.
    """

    rt = resolve_runtime(runtime)
    configured = rt.config.get("ACTIVE_PROFILE")
    if configured:
        return configured

    if rt.tent_id == DEFAULT_TENT_ID:
        return PROFILES.get("active")

    return None


def load_profiles():
    if os.path.exists(PROFILE_FILE):
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            catalog = json.load(f)

        profiles = catalog.get("profiles") if isinstance(catalog, dict) else None
        if not isinstance(profiles, dict):
            raise RuntimeError("profiles.json enthält keinen gültigen Profilkatalog")

        # Bestehende Installationen besitzen Sonnenverlauf und VPD-Werte noch
        # nicht in profiles.json. Sie werden nur im Arbeitsspeicher ergänzt und
        # erst beim nächsten bewussten Profilspeichern dauerhaft geschrieben.
        for name, settings in profiles.items():
            if not isinstance(settings, dict):
                raise RuntimeError(f"Profil {name!r} ist kein JSON-Objekt")
            compatibility = _profile_compatibility_values(settings)
            migrate_vpd_phase_config(settings, remove_legacy=True)
            for key, default in compatibility.items():
                settings.setdefault(key, deepcopy(default))

        return catalog
    raise RuntimeError("profiles.json fehlt")


def save_profiles(p):
    """Schreibt den Katalog atomar, damit nie eine halbe JSON-Datei entsteht."""

    target = Path(PROFILE_FILE)
    target_dir = target.parent

    with _PROFILE_LOCK:
        try:
            target_mode = target.stat().st_mode & 0o777
        except FileNotFoundError:
            target_mode = 0o600

        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=str(target_dir),
            text=True,
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(p, f, indent=2, ensure_ascii=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())

            os.chmod(temporary_name, target_mode)
            os.replace(temporary_name, target)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise


PROFILES = load_profiles()


def profile_catalog():
    """Defensive Kopie aller bearbeitbaren Presets."""

    with _PROFILE_LOCK:
        return deepcopy(PROFILES.get("profiles") or {})


def profile_settings_from_config(config):
    """Kopierbarer Profil-Snapshot der aktuell gespeicherten Stationswerte."""

    if not isinstance(config, dict):
        raise TypeError("Stationskonfiguration muss ein JSON-Objekt sein")

    source = deepcopy(config)
    migrate_vpd_phase_config(source, remove_legacy=True)

    return {
        key: deepcopy(source.get(key, DEFAULT_CONFIG[key]))
        for key in PROFILE_SETTING_KEYS
    }


def update_profile(name, data):
    """Speichert ein Preset, ohne irgendeine Runtime zu verändern."""

    profile_name = str(name or "").strip()

    with _PROFILE_LOCK:
        profiles = PROFILES.get("profiles") or {}
        if profile_name not in profiles:
            raise KeyError(profile_name)

        normalized = normalize_profile_settings(data)
        working = deepcopy(PROFILES)
        working["profiles"][profile_name] = normalized

        # Erst die Datei sicher ersetzen, dann die im Prozess verwendete
        # Objektidentität aktualisieren. Importierte PROFILES-Referenzen
        # bleiben dadurch gültig.
        save_profiles(working)
        PROFILES.clear()
        PROFILES.update(working)

    return deepcopy(normalized)


def apply_profile(name, runtime=None):
    """Wendet einen vorhandenen Grow-Preset auf eine Runtime an.

    ``profiles.json`` bleibt in Phase 2 noch der gemeinsame Preset-Katalog.
    Die eigentliche Config wird jedoch bereits über die Runtime geschrieben.
    Für tent_1 ist das exakt die bisherige config.json.
    """

    from core.ramp import stop_ramp

    rt = resolve_runtime(runtime)
    cfg = rt.config
    st = rt.state

    with _PROFILE_LOCK:
        if name not in PROFILES["profiles"]:
            return False

        profile = deepcopy(PROFILES["profiles"][name])

        try:
            light_sun_enabled = _finite_number(profile, "LIGHT_SUN_ENABLED")
        except ValueError as exc:
            raise ProfileActivationError(
                "profile_invalid",
                "Das Profil enthält keinen gültigen Sonnenverlauf-Schalter.",
            ) from exc

        if (
            not light_sun_enabled.is_integer()
            or int(light_sun_enabled) not in {0, 1}
        ):
            raise ProfileActivationError(
                "profile_invalid",
                "Das Profil enthält keinen gültigen Sonnenverlauf-Schalter.",
            )

        if int(light_sun_enabled):
            from core.capability_routing import controller_assignment_for_config

            try:
                assignment = controller_assignment_for_config(cfg, "light")
            except ValueError as exc:
                raise ProfileActivationError(
                    "light_sun_controller_required",
                    "Die Licht-Controller-Zuordnung dieser Station ist ungültig. "
                    "Bitte die Zuordnung vor dem Profilwechsel korrigieren.",
                ) from exc

            target_id = (
                str(assignment.get("target_id") or "").strip()
                if isinstance(assignment, dict)
                else ""
            )
            if not target_id:
                raise ProfileActivationError(
                    "light_sun_controller_required",
                    "Dieses Profil aktiviert Sonnenaufgang und Sonnenuntergang. "
                    "Dafür muss der Station zuerst ein geeigneter "
                    "Licht-Controller zugewiesen werden.",
                )

        if str(cfg.get("VPD_CONTROL_MODE", "OFF") or "OFF").upper() in {
            "MONITOR",
            "AUTO",
        }:
            from core.vpd import validate_vpd_environment_alignment

            candidate = deepcopy(cfg)
            candidate.update(profile)
            try:
                validate_vpd_environment_alignment(candidate)
            except (TypeError, ValueError) as exc:
                raise ProfileActivationError(
                    "vpd_profile_incompatible",
                    "Das VPD-Fenster dieses Profils ist mit den Schutzgrenzen "
                    f"der Station nicht vereinbar: {exc}",
                ) from exc

    for legacy_key in VPD_LEGACY_SHARED_KEYS:
        cfg.pop(legacy_key, None)

    for key, value in profile.items():
        cfg[key] = deepcopy(value)

    # Die Auswahl selbst gehört zur Station. Nur für tent_1 spiegeln wir den
    # Namen zusätzlich in profiles.json, damit bestehende Legacy-Aufrufe und
    # Backups weiterhin denselben aktiven Preset-Namen sehen.
    cfg["ACTIVE_PROFILE"] = name
    if rt.tent_id == DEFAULT_TENT_ID:
        with _PROFILE_LOCK:
            working = deepcopy(PROFILES)
            working["active"] = name
            save_profiles(working)
            PROFILES.clear()
            PROFILES.update(working)

    rt.persist_config()

    from core.vpd import reset_vpd_control
    reset_vpd_control(runtime=rt, reason=f"Profil {name} aktiviert")

    # Profilwechsel setzt die Rampe nur in der betroffenen Runtime zurück.
    st.ramp_active = False
    stop_ramp(runtime=rt)

    st.live_state["ramp_active"] = False
    st.live_state["ramp_target"] = None

    print(f"🔁 [{rt.tent_id}] Profilwechsel → Rampe zurückgesetzt ({name})")

    return True
