import datetime
import math

# =========================================
# 🌱 HILFSFUNKTIONEN
# =========================================

def calculate_vpd(temp_c, humidity):
    svp = 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
    avp = svp * (humidity / 100.0)
    return round(svp - avp, 3)

def minutes_now():
    now = datetime.datetime.now()
    return now.hour * 60 + now.minute

def is_night(now_min, night_start, day_start):
    # NACHT ist IMMER das Intervall zwischen night_start und day_start
    if night_start < day_start:
        return night_start <= now_min < day_start
    else:
        return now_min >= night_start or now_min < day_start

def in_ramp_window(now_min, target_start, ramp_duration):
    ramp_start = target_start - ramp_duration

    if ramp_start >= 0:
        return ramp_start <= now_min < target_start
    else:
        ramp_start += 1440
        return now_min >= ramp_start or now_min < target_start

def minute_distance(a, b):
    return min(
        (a - b) % 1440,
        (b - a) % 1440
    )

def in_time_window(now_min, start, end):
    if start < end:
        return start <= now_min < end
    else:
        return now_min >= start or now_min < end
