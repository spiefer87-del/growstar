"""Bounded, opt-in anticipatory control for a relay heater.

Only sensor observations from this process are used. A restart starts with
the classic thermostat until enough observations exist to predict a trend.
"""

import math
import time


MIN_DWELL_SECONDS = 4 * 60
LOOKAHEAD_SECONDS = 3 * 60
MAX_EARLY_OFF_C = 0.3


def decide(state, *, temperature, target, tolerance, enabled, now):
    """Return (requested relay state, reason); mutate only per-station memory."""
    temp = float(temperature)
    target = float(target)
    tol = max(0.0, float(tolerance))
    now = float(now)
    if not all(math.isfinite(x) for x in (temp, target, tol, now)):
        raise ValueError("Ungültige Heizregelwerte")

    previous = state.get("sample")
    rate = state.get("rate")
    # Target changes invalidate the learned off-point, e.g. a new day profile.
    if state.get("target") is not None and abs(target - state["target"]) > 0.15:
        state.clear()
        previous, rate = None, None
    state["target"] = target
    if previous is not None:
        elapsed = now - previous[0]
        if 30 <= elapsed <= 10 * 60:
            observed = (temp - previous[1]) / elapsed
            if abs(observed) <= 0.003:  # reject sudden implausible sensor jumps
                rate = observed if rate is None else 0.65 * rate + 0.35 * observed
        elif elapsed < 0 or elapsed > 10 * 60:
            rate = None
    state["sample"] = (now, temp)
    state["rate"] = rate

    last_on = state.get("last_on")
    if last_on is None or bool(last_on) != bool(enabled):
        state["last_on"] = bool(enabled)
        state["transition_at"] = now
        # A cooling slope must not inherit the previous heating slope.
        state["rate"] = None
        if not enabled and last_on is True:
            state["off_temperature"] = temp
            state["off_at"] = now
        if enabled:
            state.pop("off_temperature", None)

    off_at = state.get("off_at")
    off_temp = state.get("off_temperature")
    if not enabled and off_at is not None and off_temp is not None:
        if 0 <= now - off_at <= 8 * 60:
            coast = max(0.0, temp - off_temp)
            if coast >= 0.04:
                state["coast"] = min(MAX_EARLY_OFF_C, max(state.get("coast", 0.0) * 0.8, coast))
        elif now - off_at > 8 * 60:
            state.pop("off_temperature", None)

    # A heater that cannot reach its target must stay on continuously.
    if enabled and temp < target - 0.25:
        return True, "unter Soll, weiter heizen"

    lead = min(MAX_EARLY_OFF_C, max(0.0, float(state.get("coast", 0.0))))
    if enabled:
        forecast_rise = max(0.0, rate or 0.0) * LOOKAHEAD_SECONDS
        cutoff = target - max(lead, min(0.2, forecast_rise))
        if temp >= target + 0.1:
            return False, "Soll überschritten"
        if temp >= cutoff and now - state["transition_at"] >= MIN_DWELL_SECONDS:
            return False, "vorausschauend vor Soll abgeschaltet"
        return True, "Heizphase läuft"

    forecast = temp + min(0.0, rate or 0.0) * LOOKAHEAD_SECONDS
    # A wide classic hysteresis must not leave a weak heater idle at 26.2 °C
    # against a 26.5 °C target. Predictive mode narrows only the ON threshold.
    threshold = target - min(tol, 0.15)
    if temp < target - 0.25:
        return True, "deutlich unter Soll"
    if (temp < threshold or forecast < threshold) and now - state["transition_at"] >= MIN_DWELL_SECONDS:
        return True, "Temperaturabfall vorausberechnet" if temp >= threshold else "unter Soll"
    return False, "Heizpause"


def observe_target(runtime, *, temperature=None, target=None, active=False, now=None):
    """Emit one warning per uninterrupted 30-minute heating deficit.

    Only an actually reported ON relay counts; OFF, invalid readings and
    changes of mode end the episode. No alert is inferred from old samples.
    """
    state = runtime.heating_target_watch
    now = time.time() if now is None else float(now)
    try:
        gap = float(target) - float(temperature)
        valid = all(math.isfinite(x) for x in (gap, now))
    except (TypeError, ValueError):
        valid, gap = False, 0
    unmet = bool(active and valid and gap >= 0.2)
    if unmet:
        if state.get("target") is None or abs(state["target"] - float(target)) > 0.15:
            state.clear()
            state.update(start=now, target=float(target))
        state.setdefault("start", now)
        if now - state["start"] >= 30 * 60 and not state.get("warned"):
            from services.grow_events import enqueue_event

            queued = enqueue_event(
                station_id=runtime.tent_id, occurred_at=int(now), category="climate",
                event_type="heating_target_missed", severity="warning",
                title="Heizung erreicht Solltemperatur nicht",
                summary=(f"Die Heizung ist seit mindestens 30 Minuten eingeschaltet; "
                         f"aktuell {float(temperature):.1f} °C bei Soll {float(target):.1f} °C. "
                         "Heizleistung, Sensorposition und Luftaustausch prüfen."),
                source="heating_control", source_id="heating",
                correlation_id=f"heating:{runtime.tent_id}:{int(state['start'])}",
                dedupe_key=f"heating:missed:{runtime.tent_id}:{int(state['start'])}",
                metadata={"temperatur_c": round(float(temperature), 2),
                          "temperatur_soll_c": round(float(target), 2),
                          "dauer_min": int((now - state["start"]) // 60)},
            )
            if queued:
                state["warned"] = True
        return

    if state.get("warned"):
        from services.grow_events import enqueue_event

        reached = valid and float(temperature) >= float(state["target"]) - 0.15
        enqueue_event(
            station_id=runtime.tent_id, occurred_at=int(now), category="climate",
            event_type="heating_target_recovered", severity="info",
            title="Heizhinweis beendet",
            summary=("Temperatur liegt wieder am Sollwert." if reached else
                     "Heizanforderung beendet oder Messwert nicht mehr verfügbar."),
            source="heating_control", source_id="heating",
            correlation_id=f"heating:{runtime.tent_id}:{int(state['start'])}",
            dedupe_key=f"heating:recovered:{runtime.tent_id}:{int(state['start'])}",
        )
    state.clear()
