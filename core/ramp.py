# core/ramp.py

import time
import datetime

import core.state as state

from core.config import config
from core.helpers import minutes_now




# =========================================
# 🌡️ RAMPE STARTEN
# =========================================

def start_ramp(start_temp, target_temp, duration_min, end_min):

    now = time.time()

    end_dt = datetime.datetime.now().replace(
        hour=end_min // 60,
        minute=end_min % 60,
        second=0,
        microsecond=0,
    )

    if end_dt.timestamp() <= now:
        end_dt += datetime.timedelta(days=1)

    state.ramp_active = True

    state.ramp_start_ts = now
    state.ramp_end_ts = end_dt.timestamp()

    state.ramp_start_temp = float(start_temp)
    state.ramp_target_temp = float(target_temp)

    state.live_state["ramp_active"] = True
    state.live_state["ramp_target"] = float(target_temp)

    print(
        f"🌡️ RAMPE START "
        f"{start_temp:.1f}°C → {target_temp:.1f}°C "
        f"Ende {end_dt.strftime('%H:%M')}"
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
    """
    Wird aufgerufen wenn DAY_TEMP
    oder NIGHT_TEMP während einer
    laufenden Rampe geändert wurden.

    Laufzeit bleibt identisch.
    Aktueller Rampenwert bleibt erhalten.
    """

    if not state.ramp_active:
        return

    now = time.time()

    current = get_ramped_target()

    if current is None:
        return

    remaining = state.ramp_end_ts - now

    if remaining <= 0:
        return

    if state.current_profile == "TAG":
        new_target = float(config["NIGHT_TEMP"])
    else:
        new_target = float(config["DAY_TEMP"])

    state.ramp_start_ts = now
    state.ramp_start_temp = current

    state.ramp_target_temp = new_target

    state.ramp_end_ts = now + remaining

    state.live_state["ramp_target"] = new_target

    print(
        f"🔁 RAMPE RESYNC "
        f"{current:.1f}°C → {new_target:.1f}°C "
        f"(Rest {remaining/60:.1f}min)"
    )


# =========================================
# ⏱️ DAUER RESYNC
# =========================================

def update_ramp_duration():
    """
    Wenn RAMP_DURATION_MIN geändert wird,
    wird die verbleibende Rampenzeit
    proportional neu berechnet.

    Der aktuelle Rampenwert springt dabei nicht.
    """

    if not state.ramp_active:
        return

    now = time.time()

    old_duration = (
        state.ramp_end_ts -
        state.ramp_start_ts
    )

    if old_duration <= 0:
        return

    progress = (
        (now - state.ramp_start_ts)
        / old_duration
    )

    progress = max(
        0.0,
        min(1.0, progress)
    )

    new_duration = (
        float(config["RAMP_DURATION_MIN"])
        * 60
    )

    remaining_fraction = (
        1.0 - progress
    )

    remaining_seconds = (
        new_duration
        * remaining_fraction
    )

    state.ramp_end_ts = (
        now
        + remaining_seconds
    )

    print(
        f"⏱️ RAMPE DAUER UPDATE "
        f"neu={new_duration/60:.0f}min "
        f"rest={remaining_seconds/60:.1f}min"
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
        now_min == morning_start
        and (
            state.last_ramp_trigger_day != today
            or state.last_ramp_trigger_type != "morning"
        )
    ):
        start_ramp(
            float(config["NIGHT_TEMP"]),
            float(config["DAY_TEMP"]),
            duration,
            day_start
        )
        state.last_ramp_trigger_day = today
        state.last_ramp_trigger_type = "morning"

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
            duration,
            night_start
        )
        state.last_ramp_trigger_day = today
        state.last_ramp_trigger_type = "evening"

