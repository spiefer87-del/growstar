#!/usr/bin/env python3
"""Heater demand, station isolation, safety and target-miss regression."""

import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if "requests" not in sys.modules:
    requests = types.ModuleType("requests")
    requests.Timeout = type("Timeout", (Exception,), {})
    requests.ConnectionError = type("ConnectionError", (Exception,), {})
    requests.RequestException = type("RequestException", (Exception,), {})
    requests.get = requests.post = lambda *args, **kwargs: None
    sys.modules["requests"] = requests

from core.control import control_heating_env, control_device
from core.heating_predictive import decide, observe_target
from core.runtime import create_isolated_runtime
from services import grow_events
from services.grow_insights import _heating_target_insights


def require(value, label):
    assert value, label
    print("✅", label)


def runtime(tent_id, predictive=True):
    rt = create_isolated_runtime(tent_id, config_data={
        "DAY_TEMP": 25.0, "DAY_TEMP_TOL": 0.2,
        "MIN_TEMP": 18, "MAX_TEMP": 30,
        "DEVICE_MODES": {"heating": "ENV"},
        "DEVICE_PARAMS": {"heating": {"predictive_heating": predictive}},
    }, control_enabled=True)
    rt.state.live_state["temp"] = 24.5
    return rt


def main():
    state = {}
    # Zelt 1: a weak heater stays on well below the target; no duty cycling.
    for stamp, temp in ((0, 24.5), (300, 24.7), (600, 24.8), (900, 24.8)):
        action, _ = decide(state, temperature=temp, target=25, tolerance=.2,
                           enabled=stamp > 0, now=stamp)
        require(action, "Unter Soll ohne künstliche Heizpause")
    weak = {}
    action, _ = decide(weak, temperature=26.2, target=26.5, tolerance=.5,
                       enabled=False, now=1000)
    require(action, "Breite klassische Toleranz verhindert im neuen Modus kein Nachheizen")
    action, _ = decide(weak, temperature=26.2, target=26.5, tolerance=.5,
                       enabled=True, now=1300)
    require(action, "Zelt mit schwacher Heizung heizt bei 0,3 Grad Defizit durch")

    # Zelt 2: a measured positive trend turns off early, a falling trend
    # switches on ahead of the lower boundary, but not before dwell expires.
    state = {}
    decide(state, temperature=24.55, target=25, tolerance=.2,
           enabled=True, now=100)
    action, _ = decide(state, temperature=24.9, target=25, tolerance=.2,
                       enabled=True, now=400)
    require(not action, "Steigender Verlauf schaltet vor Sollwert ab")
    action, _ = decide(state, temperature=24.83, target=25, tolerance=.2,
                       enabled=False, now=410)
    require(not action, "Mindestabstand schützt vor schnellem Wiederanlauf")
    action, _ = decide(state, temperature=24.81, target=25, tolerance=.2,
                       enabled=False, now=720)
    require(action, "Fallender Verlauf führt zum frühen Wiederanlauf")
    require(0 <= state.get("coast", 0) <= .3, "Nachheizen ist begrenzt")

    coast_state = {}
    decide(coast_state, temperature=24.8, target=25, tolerance=.2,
           enabled=True, now=0)
    decide(coast_state, temperature=24.92, target=25, tolerance=.2,
           enabled=False, now=300)
    decide(coast_state, temperature=25.05, target=25, tolerance=.2,
           enabled=False, now=390)
    require(.12 <= coast_state["coast"] <= .14,
            "Beobachtetes Nachheizen wird je Station begrenzt gelernt")
    decide(coast_state, temperature=25.05, target=26, tolerance=.2,
           enabled=False, now=700)
    require("coast" not in coast_state, "Profilwechsel verwirft altes Heizmodell")

    one, two = runtime("tent_1"), runtime("tent_2")
    outputs = []
    def fake_set(on, reason="", runtime=None):
        runtime.state.heating_on = bool(on)
        outputs.append((runtime.tent_id, bool(on)))

    with patch("core.control.set_heating", side_effect=fake_set), patch(
        "core.control.observe_target"
    ):
        with patch("core.control.update_temperature_setpoint", side_effect=lambda runtime: runtime.state.live_state.update(temp_target=25., temp_tol=.2)):
            control_heating_env(runtime=one)
            require(outputs[-1] == ("tent_1", True), "Nur Zelt 1 fordert Wärme an")
            two.state.live_state["temp"] = 30.1
            two.state.heating_on = True
            control_heating_env(runtime=two)
            require(outputs[-1] == ("tent_2", False), "MAX TEMP schaltet auch mit intelligenter Regelung ab")
            one.state.temp_stale = True
            control_heating_env(runtime=one)
            require(outputs[-1] == ("tent_1", False), "Veralteter Sensor erzwingt AUS")

    events = []
    with patch("services.grow_events.enqueue_event", side_effect=lambda **kwargs: events.append(kwargs) or True):
        observe_target(one, temperature=26.2, target=26.5, active=True, now=1000)
        observe_target(one, temperature=26.2, target=26.5, active=True, now=2801)
        observe_target(one, temperature=26.2, target=26.5, active=True, now=3000)
        require(len(events) == 1 and events[0]["event_type"] == "heating_target_missed",
                "30 Minuten Unterversorgung erzeugen genau einen belegten Hinweis")
        observe_target(two, temperature=25, target=25, active=False, now=3001)
        require(not two.heating_target_watch, "Warnzustände sind stationsgetrennt")
        observe_target(one, temperature=26.4, target=26.5, active=True, now=3002)
        require(len(events) == 2 and events[1]["event_type"] == "heating_target_recovered",
                "Annäherung an Sollwert beendet offenen Hinweis")
    with tempfile.TemporaryDirectory(prefix="growstar-heating-") as directory:
        original_db = grow_events.DB_FILE
        grow_events.DB_FILE = Path(directory) / "events.db"
        try:
            grow_events.init_grow_event_db()
            grow_events.record_event(**events[0])
            require(len(_heating_target_insights("tent_1", {"tent_1": "Zelt 1"})) == 1,
                    "Offene Heizwarnung erscheint in Grow Intelligence")
            require(not _heating_target_insights("tent_2", {"tent_2": "Zelt 2"}),
                    "Stationsfilter versteckt Warnung anderer Stationen")
            grow_events.record_event(**events[1])
            require(not _heating_target_insights("tent_1", {"tent_1": "Zelt 1"}),
                    "Entwarnung entfernt offenen Heizhinweis")
        finally:
            grow_events.DB_FILE = original_db
    print("✅ Heizregelung und Grow-Intelligence-Hinweis geprüft")


if __name__ == "__main__":
    main()
