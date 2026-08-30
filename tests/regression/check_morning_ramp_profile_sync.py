#!/usr/bin/env python3
"""Regressionstest für synchronen Morgenstart von Profil und Heizungsrampe."""

from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import core.ramp as ramp


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    cfg = {
        "RAMP_ENABLED": 1,
        "RAMP_DURATION_MIN": 30,
        "DAY_START_MIN": 330,
        "NIGHT_START_MIN": 1050,
        "NIGHT_TEMP": 20.0,
        "DAY_TEMP": 24.0,
    }
    state = SimpleNamespace(
        ramp_active=False,
        last_ramp_trigger_day=None,
        last_ramp_trigger_type=None,
    )
    runtime = SimpleNamespace(tent_id="tent_test", config=cfg, state=state)

    original_resolve_runtime = ramp.resolve_runtime
    original_minutes_now = ramp.minutes_now
    original_start_ramp = ramp.start_ramp

    calls = []

    try:
        ramp.resolve_runtime = lambda runtime=None: runtime
        ramp.start_ramp = lambda start_temp, target_temp, end_min, runtime=None: calls.append(
            {"start_temp": start_temp, "target_temp": target_temp, "end_min": end_min}
        )

        require(ramp.get_morning_ramp_start(runtime=runtime) == 330,
                "Morgenrampe startet exakt um 05:30 mit dem Profil")
        require(ramp.get_morning_ramp_end(runtime=runtime) == 360,
                "30-Minuten-Morgenrampe endet um 06:00")
        require(ramp.get_evening_ramp_start(runtime=runtime) == 1020,
                "Abendrampe bleibt 30 Minuten vor Nachtbeginn")

        ramp.minutes_now = lambda: 300
        ramp.check_ramp_schedule(runtime=runtime)
        require(calls == [], "Um 05:00 startet keine Morgenrampe mehr")

        ramp.minutes_now = lambda: 330
        ramp.check_ramp_schedule(runtime=runtime)
        require(len(calls) == 1, "Um 05:30 wird die Morgenrampe ausgelöst")
        require(
            calls[0] == {"start_temp": 20.0, "target_temp": 24.0, "end_min": 360},
            "Morgenrampe läuft 05:30–06:00 von NIGHT_TEMP zu DAY_TEMP",
        )

        state.ramp_active = False
        state.last_ramp_trigger_day = None
        state.last_ramp_trigger_type = None
        calls.clear()

        ramp.minutes_now = lambda: 1020
        ramp.check_ramp_schedule(runtime=runtime)
        require(
            calls[0] == {"start_temp": 24.0, "target_temp": 20.0, "end_min": 1050},
            "Abendrampe bleibt 17:00–17:30 unverändert",
        )
    finally:
        ramp.resolve_runtime = original_resolve_runtime
        ramp.minutes_now = original_minutes_now
        ramp.start_ramp = original_start_ramp

    print("✅ Growstar 3.15.5 / RAMP.SYNC.1 vollständig geprüft")


if __name__ == "__main__":
    main()
