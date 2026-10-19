#!/usr/bin/env python3
"""Station sensor fallback: validation, failover, recovery and safe failure."""

import ast
import math
import sys
import time
from pathlib import Path
from threading import RLock
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import sensor_sources


def require(condition, description):
    assert condition, description
    print("✅", description)


def station(tent_id, assignments):
    return SimpleNamespace(
        tent_id=tent_id,
        config={"SENSOR_ASSIGNMENTS": assignments},
        state=SimpleNamespace(
            live_state={}, last_ds_time=0, last_dht_time=0,
            temp_stale=True, hum_stale=True,
        ),
        state_lock=RLock(),
    )


def main():
    path = ROOT / "routes/sensors.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in ("_normalize_assignment", "_normalize_optional_assignment",
                                   "_save_assignments", "_offsets")]
    route = {"_RETIRED_SOURCE_IDS": set(), "math": math,
             "_OFFSET_KEYS": ("TEMP_OFFSET", "HUM_OFFSET", "OUTSIDE_TEMP_OFFSET", "OUTSIDE_HUM_OFFSET"),
             "reset_vpd_control": lambda **kwargs: None,
             "apply_sensor_assignments": lambda runtime=None: True}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), route)
    normalize = route["_normalize_assignment"]
    primary = {"source_id": "mqtt:first", "field": "temperature", "label": "Erster"}
    fallback = {"source_id": "mqtt:second", "field": "temperature", "label": "Zweiter"}
    assignment = normalize("temperature", {**primary, "fallback": fallback})
    require(assignment["fallback"] == fallback, "Fallback wird getrennt vom Primärsensor gespeichert")
    for invalid in (primary, {"source_id": "mqtt:second", "field": "humidity"},
                    {**fallback, "fallback": primary}):
        try:
            normalize("temperature", {**primary, "fallback": invalid})
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError(f"Ungültiger Fallback akzeptiert: {invalid}")
    require(True, "Gleicher Sensor, falscher Kanal und Kaskaden werden abgewiesen")

    saved = station("tent_1", {"humidity": {"source_id": "mqtt:humid", "field": "humidity"}})
    saved.persist_config = lambda: None
    route["_save_assignments"](saved, {"temperature": {**primary, "fallback": fallback}})
    require(saved.config["SENSOR_ASSIGNMENTS"]["temperature"]["fallback"] == fallback and
            "humidity" in saved.config["SENSOR_ASSIGNMENTS"],
            "Speichern übernimmt den Fallback und erhält die übrigen Messgrößen")

    now = time.time()
    sources = {
        "mqtt:first": {"temperature": 24.0, "last_seen": now},
        "mqtt:second": {"temperature": 23.7, "last_seen": now},
        "mqtt:third": {"temperature": 28.0, "last_seen": now},
        "mqtt:humid": {"humidity": 52.0, "last_seen": now},
    }
    first = station("tent_1", {"temperature": assignment,
                               "humidity": {"source_id": "mqtt:humid", "field": "humidity",
                                            "fallback": {"source_id": "mqtt:second_hum", "field": "humidity"}}})
    sources["mqtt:second_hum"] = {"humidity": 50.0, "last_seen": now}
    second = station("tent_2", {"temperature": {"source_id": "mqtt:third", "field": "temperature"}})
    with patch.object(sensor_sources, "resolve_runtime", side_effect=lambda rt: rt), \
         patch.object(sensor_sources, "get_sensor_source", side_effect=lambda key: sources.get(key)):
        sensor_sources.apply_sensor_assignments(first)
        require(first.state.live_state["temp"] == 24.0 and
                not first.state.live_state["sensor_fallbacks"]["temperature"],
                "Bei gesunder Primärquelle bleibt sie zuständig")

        sources["mqtt:humid"]["humidity"] = 140.0
        sensor_sources.apply_sensor_assignments(first)
        require(first.state.live_state["hum"] == 50.0 and
                first.state.live_state["sensor_fallbacks"]["humidity"],
                "Feuchte außerhalb 0–100 Prozent löst ebenfalls den Fallback aus")
        sources["mqtt:humid"]["humidity"] = 52.0

        sources["mqtt:first"]["last_seen"] = now - sensor_sources.SENSOR_TIMEOUT - 1
        sensor_sources.apply_sensor_assignments(first)
        require(first.state.live_state["temp"] == 23.7 and
                first.state.live_state["sensor_fallbacks"]["temperature"] and
                first.state.live_state["sensor_active_sources"]["temperature"] == "mqtt:second" and
                not first.state.temp_stale and first.state.last_ds_time >= now,
                "Ein alter Primärwert schaltet auf den frischen Fallback um")

        sources["mqtt:first"].update(last_seen=time.time(), temperature=math.nan)
        sensor_sources.apply_sensor_assignments(first)
        require(first.state.live_state["temp"] == 23.7,
                "Ein ungültiger Primärwert darf den Fallback nicht verdrängen")

        sources["mqtt:first"]["temperature"] = 24.2
        sensor_sources.apply_sensor_assignments(first)
        require(first.state.live_state["temp"] == 24.2 and
                not first.state.live_state["sensor_fallbacks"]["temperature"],
                "Nach Erholung kehrt die Primärquelle automatisch zurück")

        sources["mqtt:first"]["temperature"] = math.nan
        sources["mqtt:second"]["last_seen"] = now - sensor_sources.SENSOR_TIMEOUT - 1
        sensor_sources.apply_sensor_assignments(first)
        require(first.state.live_state["temp"] is None and first.state.temp_stale and
                first.state.last_ds_time == 0 and
                first.state.live_state["sensor_active_sources"]["temperature"] is None,
                "Bei Ausfall beider Quellen wird kein alter Regelwert behalten")
        sensor_sources.apply_sensor_assignments(second)
        require(second.state.live_state["temp"] == 28.0 and
                first.state.live_state["hum"] == 52.0,
                "Andere Stationen und Messgrößen bleiben unabhängig")

    ui = (ROOT / "templates/grow_control_setup.html").read_text()
    require('class="fallback-select"' in ui and 'Fallback gerade aktiv' in ui and
            'Kein Fallback' in ui,
            "Setup zeigt optionale Sekundärquelle und aktiven Wechsel an")
    print("✅ SENSOR.FALLBACK.1 erfolgreich")


if __name__ == "__main__":
    main()
