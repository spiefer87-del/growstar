# core/profile.py

import os
import json
import datetime

import core.state as state

from core.config import config, save_config
from core.helpers import (
    minutes_now,
    is_night,
    minute_distance
)



def get_profile():

    now_min = minutes_now()

    day_start = int(config["DAY_START_MIN"])
    night_start = int(config["NIGHT_START_MIN"])

    if is_night(now_min, night_start, day_start):
        profile = "NACHT"
    else:
        profile = "TAG"

    if profile != state.current_profile:
        print(
            f"🔄 Profilwechsel: "
            f"{state.current_profile} -> {profile} "
            f"({minutes_now()} min)"
        )
        state.current_profile = profile

    state.live_state["profile"] = profile

    return profile

PROFILE_FILE = "profiles.json"

def get_active_profile():
    return PROFILES.get("active")

def load_profiles():
    if os.path.exists(PROFILE_FILE):
        with open(PROFILE_FILE, "r") as f:
            return json.load(f)
    raise RuntimeError("profiles.json fehlt")

def save_profiles(p):
    with open(PROFILE_FILE, "w") as f:
        json.dump(p, f, indent=2)

PROFILES = load_profiles()

def apply_profile(name):
    from core.ramp import stop_ramp

    if name not in PROFILES["profiles"]:
        return False

    PROFILES["active"] = name
    profile = PROFILES["profiles"][name]

    # 🔁 Profilwerte ins config übernehmen
    for k, v in profile.items():
        config[k] = v

    # 💾 speichern
    save_profiles(PROFILES)
    save_config(config)

    # =========================
    # 🔄 SCHRITT 4: Rampe zurücksetzen
    # =========================
    state.ramp_active = False
    stop_ramp()

    state.live_state["ramp_active"] = False
    state.live_state["ramp_target"] = None

    print(f"🔁 Profilwechsel → Rampe zurückgesetzt ({name})")

    return True

