"""Daily minute-resolution relay windows for the Zeitschaltuhr mode."""

MAX_WINDOWS = 12


def validate_timer_windows(windows, *, require_one=False):
    """Normalize and reject incomplete, overlapping or all-day windows.

    Endpoints are exclusive, so 21:00–21:03 runs for exactly three minutes.
    Windows crossing midnight are split only for overlap checking; the saved
    window retains its original start/end for display.
    """
    if not isinstance(windows, list) or len(windows) > MAX_WINDOWS:
        raise ValueError(f"Zeitschaltuhr: höchstens {MAX_WINDOWS} Zeitfenster erlaubt")
    if require_one and not windows:
        raise ValueError("Zeitschaltuhr: mindestens ein Zeitfenster eingeben")

    normalized, spans = [], []
    for number, window in enumerate(windows, 1):
        if not isinstance(window, dict):
            raise ValueError(f"Zeitfenster {number}: Start und Ende fehlen")
        start, end = window.get("start_min"), window.get("end_min")
        if (type(start) is not int or type(end) is not int
                or not 0 <= start < 1440 or not 0 <= end < 1440):
            raise ValueError(f"Zeitfenster {number}: gültige Uhrzeiten zwischen 00:00 und 23:59 eingeben")
        if start == end:
            raise ValueError(f"Zeitfenster {number}: Start und Ende dürfen nicht gleich sein")
        normalized.append({"start_min": start, "end_min": end})
        if start < end:
            spans.append((start, end))
        else:
            spans.extend(((start, 1440), (0, end)))

    spans.sort()
    if any(left[1] > right[0] for left, right in zip(spans, spans[1:])):
        raise ValueError("Zeitschaltuhr: Zeitfenster dürfen sich nicht überschneiden")
    return sorted(normalized, key=lambda window: window["start_min"])


def timer_is_on(windows, minute):
    """Fail closed on corrupt configuration or an invalid clock reading."""
    try:
        valid = validate_timer_windows(windows, require_one=True)
        if type(minute) is not int or not 0 <= minute < 1440:
            return False
    except ValueError:
        return False
    return any(
        start <= minute < end if start < end else minute >= start or minute < end
        for window in valid
        for start, end in ((window["start_min"], window["end_min"]),)
    )
