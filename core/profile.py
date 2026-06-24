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
