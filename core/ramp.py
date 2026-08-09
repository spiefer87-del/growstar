# core/ramp.py

import time
import datetime

from core.runtime import resolve_runtime
from core.helpers import minutes_now
from core.profile import get_profile


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


def _restart_ramp(current_temp, target_temp, end_min, runtime=None):
    """Startet eine laufende Rampe mit neuem Startwert neu."""

    rt = resolve_runtime(runtime)
    st = rt.state

    st.ramp_start_ts = time.time()
    st.ramp_end_ts = get_ramp_end_timestamp(end_min)

    st.ramp_start_temp = float(current_temp)
    st.ramp_target_temp = float(target_temp)

    st.live_state["ramp_target"] = float(target_temp)

    print(
        f"🔁 [{rt.tent_id}] RAMPE UPDATE "
        f"{current_temp:.2f}°C → {target_temp:.2f}°C "
        f"Ende "
        f"{datetime.datetime.fromtimestamp(st.ramp_end_ts).strftime('%H:%M')}"
    )


# =========================================
# 🌡️ RAMPE STARTEN
# =========================================

def start_ramp(start_temp, target_temp, end_min, runtime=None):
    rt = resolve_runtime(runtime)
    st = rt.state

    now = time.time()

    st.ramp_active = True
    st.ramp_start_ts = now
    st.ramp_end_ts = get_ramp_end_timestamp(end_min)
    st.ramp_start_temp = float(start_temp)
    st.ramp_target_temp = float(target_temp)

    st.live_state["ramp_active"] = True
    st.live_state["ramp_target"] = float(target_temp)

    print(
        f"🌡️ [{rt.tent_id}] RAMPE START "
        f"{start_temp:.1f}°C → {target_temp:.1f}°C "
        f"Ende "
        f"{datetime.datetime.fromtimestamp(st.ramp_end_ts).strftime('%H:%M')}"
    )


# =========================================
# 🌡️ AKTUELLEN RAMPENWERT BERECHNEN
# =========================================

def get_ramped_target(runtime=None):
    rt = resolve_runtime(runtime)
    st = rt.state

    if not st.ramp_active:
        return None

    start_ts = st.ramp_start_ts
    end_ts = st.ramp_end_ts
    start_temp = st.ramp_start_temp
    target_temp = st.ramp_target_temp

    if None in (start_ts, end_ts, start_temp, target_temp):
        return target_temp

    duration = end_ts - start_ts
    if duration <= 0:
        return target_temp

    now = time.time()
    progress = (now - start_ts) / duration
    progress = max(0.0, min(1.0, progress))

    value = start_temp + (target_temp - start_temp) * progress
    return round(value, 2)


# =========================================
# 🔄 RAMPE AKTUALISIEREN
# =========================================

def update_ramp(runtime=None):
    rt = resolve_runtime(runtime)
    st = rt.state

    if not st.ramp_active:
        return

    if st.ramp_end_ts is None or time.time() < st.ramp_end_ts:
        return

    if st.ramp_target_temp is not None:
        print(f"✅ [{rt.tent_id}] RAMPE ENDE ({st.ramp_target_temp:.1f}°C)")
    else:
        print(f"✅ [{rt.tent_id}] RAMPE ENDE")

    stop_ramp(runtime=rt)


# =========================================
# 🔁 SOLLWERT RESYNC
# =========================================

def resync_active_ramp(runtime=None):
    rt = resolve_runtime(runtime)
    st = rt.state
    cfg = rt.config

    if not st.ramp_active:
        return

    current = get_ramped_target(runtime=rt)
    if current is None:
        return

    profile = get_profile(runtime=rt)

    if profile == "TAG":
        target = float(cfg["DAY_TEMP"])
        end_min = int(cfg["DAY_START_MIN"])
    else:
        target = float(cfg["NIGHT_TEMP"])
        end_min = int(cfg["NIGHT_START_MIN"])

    _restart_ramp(
        current,
        target,
        end_min,
        runtime=rt,
    )


# =========================================
# ⏱️ DAUER RESYNC
# =========================================

def update_ramp_duration(runtime=None):
    rt = resolve_runtime(runtime)
    st = rt.state
    cfg = rt.config

    if not st.ramp_active:
        return

    current = get_ramped_target(runtime=rt)
    if current is None:
        return

    profile = get_profile(runtime=rt)

    if profile == "TAG":
        end_min = int(cfg["DAY_START_MIN"])
    else:
        end_min = int(cfg["NIGHT_START_MIN"])

    _restart_ramp(
        current,
        st.ramp_target_temp,
        end_min,
        runtime=rt,
    )


# =========================================
# 🛑 RAMPE STOPPEN
# =========================================

def stop_ramp(runtime=None):
    rt = resolve_runtime(runtime)
    st = rt.state

    st.ramp_active = False
    st.ramp_start_ts = None
    st.ramp_end_ts = None
    st.ramp_start_temp = None
    st.ramp_target_temp = None

    st.live_state["ramp_active"] = False
    st.live_state["ramp_target"] = None

    print(f"🛑 [{rt.tent_id}] RAMPE GESTOPPT")


def get_morning_ramp_start(runtime=None):
    rt = resolve_runtime(runtime)
    cfg = rt.config
    day_start = int(cfg["DAY_START_MIN"])
    duration = int(cfg["RAMP_DURATION_MIN"])
    return (day_start - duration) % 1440


def get_evening_ramp_start(runtime=None):
    rt = resolve_runtime(runtime)
    cfg = rt.config
    night_start = int(cfg["NIGHT_START_MIN"])
    duration = int(cfg["RAMP_DURATION_MIN"])
    return (night_start - duration) % 1440


def check_ramp_schedule(runtime=None):
    rt = resolve_runtime(runtime)
    st = rt.state
    cfg = rt.config

    if not cfg.get("RAMP_ENABLED", 0):
        return

    if st.ramp_active:
        return

    now_min = minutes_now()
    today = datetime.date.today().isoformat()

    day_start = int(cfg["DAY_START_MIN"])
    night_start = int(cfg["NIGHT_START_MIN"])

    morning_start = get_morning_ramp_start(runtime=rt)
    evening_start = get_evening_ramp_start(runtime=rt)

    # 🌅 Morgenrampe
    if (
        now_min == morning_start
        and (
            st.last_ramp_trigger_day != today
            or st.last_ramp_trigger_type != "morning"
        )
    ):
        start_ramp(
            float(cfg["NIGHT_TEMP"]),
            float(cfg["DAY_TEMP"]),
            day_start,
            runtime=rt,
        )

        st.last_ramp_trigger_day = today
        st.last_ramp_trigger_type = "morning"
        return

    # 🌙 Abendrampe
    if (
        now_min == evening_start
        and (
            st.last_ramp_trigger_day != today
            or st.last_ramp_trigger_type != "evening"
        )
    ):
        start_ramp(
            float(cfg["DAY_TEMP"]),
            float(cfg["NIGHT_TEMP"]),
            night_start,
            runtime=rt,
        )

        st.last_ramp_trigger_day = today
        st.last_ramp_trigger_type = "evening"
