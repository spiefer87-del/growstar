"""Provider-neutral sunrise/sunset light curve for Growstar."""

MINUTES_PER_DAY = 1440

def _minute(value):
    return int(value) % MINUTES_PER_DAY

def _duration(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0

def calculate_light_sun_state(
    *,
    now_min,
    day_start,
    night_start,
    sunrise_duration,
    sunset_duration,
    min_level,
    target_level,
):
    now_min = _minute(now_min)
    day_start = _minute(day_start)
    night_start = _minute(night_start)

    daylight = (night_start - day_start) % MINUTES_PER_DAY
    if daylight <= 0:
        return {"on": False, "phase": "night", "level": None, "progress": 0.0}

    elapsed = (now_min - day_start) % MINUTES_PER_DAY
    if elapsed >= daylight:
        return {"on": False, "phase": "night", "level": None, "progress": 0.0}

    sunrise = min(_duration(sunrise_duration), daylight)
    sunset = min(_duration(sunset_duration), daylight)

    target = max(1, int(round(float(target_level))))
    minimum = max(1, int(round(float(min_level))))
    minimum = min(minimum, target)

    remaining = daylight - elapsed

    up = 1.0
    if sunrise > 0 and elapsed < sunrise:
        up = max(0.0, min(1.0, elapsed / float(sunrise)))

    down = 1.0
    if sunset > 0 and remaining <= sunset:
        down = max(0.0, min(1.0, remaining / float(sunset)))

    factor = max(0.0, min(1.0, min(up, down)))
    level = int(round(minimum + (target - minimum) * factor))
    level = max(minimum, min(target, level))

    if sunrise > 0 and elapsed < sunrise and up <= down:
        phase = "sunrise"
    elif sunset > 0 and remaining <= sunset:
        phase = "sunset"
    else:
        phase = "day"

    return {
        "on": True,
        "phase": phase,
        "level": level,
        "progress": round(factor, 4),
    }
