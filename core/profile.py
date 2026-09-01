# core/profile.py

import os
import json
from copy import deepcopy
import math
from pathlib import Path
import tempfile
import threading

from core.runtime import resolve_runtime
from core.tents import DEFAULT_TENT_ID
from core.helpers import (
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
)

_PROFILE_LOCK = threading.RLock()


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
            return json.load(f)
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

    # Profilwechsel setzt die Rampe nur in der betroffenen Runtime zurück.
    st.ramp_active = False
    stop_ramp(runtime=rt)

    st.live_state["ramp_active"] = False
    st.live_state["ramp_target"] = None

    print(f"🔁 [{rt.tent_id}] Profilwechsel → Rampe zurückgesetzt ({name})")

    return True
