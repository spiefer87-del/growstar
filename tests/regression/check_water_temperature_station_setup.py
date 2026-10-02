#!/usr/bin/env python3
"""Water temperature is optional, fresh, station-scoped, and historically stored."""

import sqlite3
import ast
import math
import sys
import tempfile
import time
from pathlib import Path
from threading import RLock
from types import SimpleNamespace
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import db
from core import sensor_sources


def require(condition, message):
    assert condition, message
    print("✅", message)


def station(tent_id, source_id):
    return SimpleNamespace(
        tent_id=tent_id,
        config={"SENSOR_ASSIGNMENTS": {
            "water_temperature": {
                "source_id": source_id,
                "field": "temperature",
                "label": "Tankfühler",
            },
        }},
        state=SimpleNamespace(live_state={}),
        state_lock=RLock(),
    )


def main():
    sensor_route = ROOT / "routes/sensors.py"
    tree = ast.parse(sensor_route.read_text(), filename=str(sensor_route))
    names = {"_supports", "_sensor_options", "_normalize_assignment",
             "_normalize_optional_assignment", "_save_assignments", "_offsets"}
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    namespace = {
        "math": math,
        "_RETIRED_SOURCE_IDS": set(),
        "_OFFSET_KEYS": ("TEMP_OFFSET", "HUM_OFFSET", "OUTSIDE_TEMP_OFFSET", "OUTSIDE_HUM_OFFSET"),
        "reset_vpd_control": lambda **kwargs: None,
    }
    exec(compile(ast.Module(body=funcs, type_ignores=[]), str(sensor_route), "exec"), namespace)
    namespace["_source_map"] = lambda: {
        "mqtt:tank_1": {"id": "mqtt:tank_1", "label": "Tankfühler", "temperature": 21.4},
    }
    namespace["apply_sensor_assignments"] = lambda runtime=None: True
    options = namespace["_sensor_options"]()
    require(options["water_temperature"][0]["source_id"] == "mqtt:tank_1",
            "Temperaturquellen erscheinen in der Wassersensor-Auswahl")
    configuration = {"SENSOR_ASSIGNMENTS": {"humidity": {
        "source_id": "mqtt:climate", "field": "humidity", "label": "Klima"}}}
    config_runtime = SimpleNamespace(tent_id="tent_1", config=configuration,
                                     state=SimpleNamespace(live_state={}),
                                     state_lock=RLock(), persist_config=lambda: None)
    namespace["_save_assignments"](config_runtime, {"water_temperature": {
        "source_id": "mqtt:tank_1", "field": "temperature", "label": "Tankfühler"}})
    require(configuration["SENSOR_ASSIGNMENTS"]["water_temperature"]["field"] == "temperature" and
            "humidity" in configuration["SENSOR_ASSIGNMENTS"],
            "Die optionale Tankzuweisung speichert den Temperaturkanal ohne andere Zuordnungen zu ändern")
    try:
        namespace["_normalize_assignment"]("water_temperature", {
            "source_id": "mqtt:tank_1", "field": "humidity"})
    except ValueError:
        pass
    else:
        raise AssertionError("Feuchtekanal wurde als Wassertemperatur akzeptiert")
    namespace["_save_assignments"](config_runtime, {"water_temperature": None})
    require("water_temperature" not in configuration["SENSOR_ASSIGNMENTS"] and
            "humidity" in configuration["SENSOR_ASSIGNMENTS"],
            "Tankzuweisung lässt sich einzeln wieder entfernen")

    now = time.time()
    sources = {
        "mqtt:tank_1": {"temperature": 21.4, "last_seen": now, "label": "Tank 1"},
        "mqtt:tank_2": {"temperature": 19.8, "last_seen": now, "label": "Tank 2"},
    }
    first, second = station("tent_1", "mqtt:tank_1"), station("tent_2", "mqtt:tank_2")
    with patch.object(sensor_sources, "resolve_runtime", side_effect=lambda rt: rt), \
         patch.object(sensor_sources, "get_sensor_source", side_effect=lambda key: sources.get(key)):
        sensor_sources.apply_sensor_assignments(first)
        sensor_sources.apply_sensor_assignments(second)
        require(first.state.live_state["water_temp"] == 21.4 and
                second.state.live_state["water_temp"] == 19.8,
                "Jede Station liest nur ihren zugewiesenen Tankfühler")
        require(first.state.live_state["water_temp_source"]["source_id"] == "mqtt:tank_1",
                "Die sichtbare Temperatur enthält die nachvollziehbare Quelle")
        sources["mqtt:tank_1"]["last_seen"] = now - sensor_sources.SENSOR_TIMEOUT - 5
        sensor_sources.apply_sensor_assignments(first)
        require(first.state.live_state["water_temp"] is None and
                first.state.live_state["water_temp_source"] is None,
                "Ein veralteter Tankwert bleibt nicht als aktueller Wert stehen")
        require(second.state.live_state["water_temp"] == 19.8,
                "Der Sensorausfall einer Station berührt die andere nicht")

    if "flask" not in sys.modules:
        flask = types.ModuleType("flask")
        flask.jsonify = lambda *args, **kwargs: args[0] if args else kwargs
        flask.request = SimpleNamespace(args={})
        flask.send_file = lambda *args, **kwargs: None
        sys.modules["flask"] = flask
    from routes import diagrams
    with tempfile.TemporaryDirectory() as folder:
        db_path = Path(folder) / "history.db"
        previous = db.DB_FILE
        db.DB_FILE = str(db_path)
        try:
            db.init_db()
            db.insert_measurement(None, None, water_temp=21.4, tent_id="tent_1")
            db.insert_measurement(None, None, water_temp=19.8, tent_id="tent_2")
            connect = sqlite3.connect
            with patch.object(diagrams.sqlite3, "connect", side_effect=lambda *_: connect(db_path)):
                one = diagrams._history_rows("tent_1", "1h", "water_temp")
                two = diagrams._history_rows("tent_2", "1h", "water_temp")
            require([row["water_temp"] for row in one] == [21.4] and
                    [row["water_temp"] for row in two] == [19.8],
                    "SQLite-Migration und Diagrammverlauf bleiben stationsgetrennt")
        finally:
            db.DB_FILE = previous

    setup = (ROOT / "templates/grow_control_setup.html").read_text()
    dashboard = (ROOT / "templates/grow_control.html").read_text()
    chart = (ROOT / "templates/environment_history.html").read_text()
    require('id="station-switch"' in setup and 'selected ? card(selected, defaultTentId)' in setup,
            "Setup zeigt eine ausgewählte Station mit Umschalter")
    require('water_temperature' in setup and 'Grow Station Setup' in setup,
            "Wassertemperatur ist im Grow Station Setup zuweisbar")
    require('safeText("water-temp", Number.isFinite(optionalNumber(state.water_temp))' in dashboard and
            'grow_control_tent_compare' in dashboard,
            "Dashboard-Kachel zeigt den Livewert und öffnet den Stationsvergleich")
    require('data-metric="water_temp"' in chart and 'water-temperature' in chart,
            "Diagrammseite besitzt den Wassertemperatur-Reiter")
    print("✅ WATER.TEMP.SETUP.1 erfolgreich")


if __name__ == "__main__":
    main()
