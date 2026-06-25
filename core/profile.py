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

from core.ramp import (
    start_ramp,
    stop_ramp
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

def check_ramp_schedule():

    if not config.get("RAMP_ENABLED", 0):
        return

    now_min = minutes_now()
    today = datetime.date.today().isoformat()

    day_start = int(config["DAY_START_MIN"])
    night_start = int(config["NIGHT_START_MIN"])
    duration = int(config["RAMP_DURATION_MIN"])

    evening_start = (night_start - duration) % 1440
    morning_start = (day_start - duration) % 1440

    # Bereits aktiv?
    if state.ramp_active:
        return

    if (
        minute_distance(now_min, morning_start) <= 1
        and (
            state.last_ramp_trigger_day != today
            or state.last_ramp_trigger_type != "morning"
        )
    ):
        start_ramp(
            float(config["NIGHT_TEMP"]),
            float(config["DAY_TEMP"]),
            duration
        )
        state.last_ramp_trigger_day = today
        state.last_ramp_trigger_type = "morning"

    if (
        minute_distance(now_min, evening_start) <= 1
        and (
            state.last_ramp_trigger_day != today
            or state.last_ramp_trigger_type != "evening"
        )
    ):
        start_ramp(
            float(config["DAY_TEMP"]),
            float(config["NIGHT_TEMP"]),
            duration
        )
        state.last_ramp_trigger_day = today
        state.last_ramp_trigger_type = "evening"

