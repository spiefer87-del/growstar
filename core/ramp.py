# core/ramp.py

import time
import datetime

import core.state as state

from core.config import config
from core.helpers import minutes_now


def get_ramp_end_timestamp(end_min):

    now = datetime.datetime.now()

    end_dt = now.replace(
        hour=end_min // 60,
        minute=end_min % 60,
        second=0,
        microsecond=0,
    )

    if end_dt <= now:
        end_dt += datetime.timedelta(days=1)

    return end_dt.timestamp()

def _restart_ramp(current_temp, target_temp, end_min):
    """
    Startet eine bereits laufende Rampe
    mit neuem Startwert neu.

    Die Ziel-Uhrzeit bleibt erhalten.
    """

    state.ramp_start_ts = time.time()
    state.ramp_end_ts = get_ramp_end_timestamp(end_min)

    state.ramp_start_temp = float(current_temp)
    state.ramp_target_temp = float(target_temp)

    state.live_state["ramp_target"] = float(target_temp)

    print(
        f"🔁 RAMPE UPDATE "
        f"{current_temp:.2f}°C → {target_temp:.2f}°C "
        f"Ende "
        f"{datetime.datetime.fromtimestamp(state.ramp_end_ts).strftime('%H:%M')}"
    )

# =========================================
# 🌡️ RAMPE STARTEN
# =========================================

def start_ramp(start_temp, target_temp, duration_min, end_min):

    now = time.time()

    

    state.ramp_active = True

    state.ramp_start_ts = now
    
    state.ramp_end_ts = get_ramp_end_timestamp(end_min)
    state.ramp_start_temp = float(start_temp)
    state.ramp_target_temp = float(target_temp)

    state.live_state["ramp_active"] = True
    state.live_state["ramp_target"] = float(target_temp)

    print(
        f"🌡️ RAMPE START "
        f"{start_temp:.1f}°C → {target_temp:.1f}°C "
        f"Ende "
        f"{datetime.datetime.fromtimestamp(state.ramp_end_ts).strftime('%H:%M')}"
    )


# =========================================
# 🌡️ AKTUELLEN RAMPENWERT BERECHNEN
# =========================================

def get_ramped_target():
    """
    Liefert den aktuell interpolierten Rampenwert.
    """

    if not state.ramp_active:
        return None

    start_ts = state.ramp_start_ts
    end_ts = state.ramp_end_ts

    start_temp = state.ramp_start_temp
    target_temp = state.ramp_target_temp

    if None in (
        start_ts,
        end_ts,
        start_temp,
        target_temp
    ):
        return target_temp

    duration = end_ts - start_ts

    if duration <= 0:
        return target_temp

    now = time.time()

    progress = (now - start_ts) / duration

    progress = max(0.0, min(1.0, progress))

    value = (
        start_temp
        + (target_temp - start_temp) * progress
    )

    return round(value, 2)


# =========================================
# 🔄 RAMPE AKTUALISIEREN
# =========================================

def update_ramp():

    if not state.ramp_active:
        return

    if time.time() < state.ramp_end_ts:
        return

    target = state.ramp_target_temp

    print(f"✅ RAMPE ENDE ({target:.1f}°C)")
    
    stop_ramp()


# =========================================
# 🔁 SOLLWERT RESYNC
# =========================================

def resync_active_ramp():

    if not state.ramp_active:
        return

    current = get_ramped_target()

    if current is None:
        return

    profile = get_profile()

    if profile == "TAG":
        target = float(config["DAY_TEMP"])
        end_min = int(config["DAY_START_MIN"])
    else:
        target = float(config["NIGHT_TEMP"])
        end_min = int(config["NIGHT_START_MIN"])

    _restart_ramp(
        current,
        target,
        end_min,
    )


# =========================================
# ⏱️ DAUER RESYNC
# =========================================

def update_ramp_duration():

    if not state.ramp_active:
        return

    current = get_ramped_target()

    if current is None:
        return

    profile = get_profile()

    if profile == "TAG":
        end_min = int(config["DAY_START_MIN"])
    else:
        end_min = int(config["NIGHT_START_MIN"])

    _restart_ramp(
        current,
        state.ramp_target_temp,
        end_min,
    )

# =========================================
# 🛑 RAMPE STOPPEN
# =========================================

def stop_ramp():
    """
    Vollständiger Rampen-Reset.
    """

    state.ramp_active = False

    state.ramp_start_ts = None
    state.ramp_end_ts = None

    state.ramp_start_temp = None
    state.ramp_target_temp = None

    state.live_state["ramp_active"] = False
    state.live_state["ramp_target"] = None
    state.live_state["temp_target"] = None

    print("🛑 RAMPE GESTOPPT")

def get_morning_ramp_start():
    day_start = int(config["DAY_START_MIN"])
    duration = int(config["RAMP_DURATION_MIN"])
    return (day_start - duration) % 1440


def get_evening_ramp_start():
    night_start = int(config["NIGHT_START_MIN"])
    duration = int(config["RAMP_DURATION_MIN"])
    return (night_start - duration) % 1440

def check_ramp_schedule():

    if not config.get("RAMP_ENABLED", 0):
        return

    if state.ramp_active:
        return

    now_min = minutes_now()
    today = datetime.date.today().isoformat()

    day_start = int(config["DAY_START_MIN"])
    night_start = int(config["NIGHT_START_MIN"])

    morning_start = get_morning_ramp_start()
    evening_start = get_evening_ramp_start()

    # 🌅 Morgenrampe
    if (
        now_min == morning_start
        and (
            state.last_ramp_trigger_day != today
            or state.last_ramp_trigger_type != "morning"
        )
    ):

        start_ramp(
            float(config["NIGHT_TEMP"]),
            float(config["DAY_TEMP"]),
            int(config["RAMP_DURATION_MIN"]),
            day_start,
        )

        state.last_ramp_trigger_day = today
        state.last_ramp_trigger_type = "morning"
        return

    # 🌙 Abendrampe
    if (
        now_min == evening_start
        and (
            state.last_ramp_trigger_day != today
            or state.last_ramp_trigger_type != "evening"
        )
    ):

        start_ramp(
            float(config["DAY_TEMP"]),
            float(config["NIGHT_TEMP"]),
            int(config["RAMP_DURATION_MIN"]),
            night_start,
        )

        state.last_ramp_trigger_day = today
        state.last_ramp_trigger_type = "evening"
