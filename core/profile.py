# core/profile.py

import os
import json
from copy import deepcopy

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
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(p, f, indent=2, ensure_ascii=False)


PROFILES = load_profiles()


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

    if name not in PROFILES["profiles"]:
        return False

    profile = PROFILES["profiles"][name]

    for key, value in profile.items():
        cfg[key] = deepcopy(value)

    # Die Auswahl selbst gehört zur Station. Nur für tent_1 spiegeln wir den
    # Namen zusätzlich in profiles.json, damit bestehende Legacy-Aufrufe und
    # Backups weiterhin denselben aktiven Preset-Namen sehen.
    cfg["ACTIVE_PROFILE"] = name
    if rt.tent_id == DEFAULT_TENT_ID:
        PROFILES["active"] = name
        save_profiles(PROFILES)

    rt.persist_config()

    # Profilwechsel setzt die Rampe nur in der betroffenen Runtime zurück.
    st.ramp_active = False
    stop_ramp(runtime=rt)

    st.live_state["ramp_active"] = False
    st.live_state["ramp_target"] = None

    print(f"🔁 [{rt.tent_id}] Profilwechsel → Rampe zurückgesetzt ({name})")

    return True
