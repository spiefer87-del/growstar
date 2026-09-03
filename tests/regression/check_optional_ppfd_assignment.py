#!/usr/bin/env python3
"""Optionale PPFD- und Außenquellen bleiben sicher manuell zuweisbar."""

from pathlib import Path
import ast
import math
import threading


ROOT = Path(__file__).resolve().parents[2]
SENSORS_PATH = ROOT / "routes/sensors.py"


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def load_assignment_functions():
    source = SENSORS_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SENSORS_PATH))
    names = {
        "_supports",
        "_sensor_options",
        "_normalize_assignment",
        "_normalize_optional_assignment",
        "_offsets",
        "_save_assignments",
    }
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]

    require(
        {node.name for node in functions} == names,
        "Alle geprüften Sensor-Zuweisungsfunktionen sind vorhanden",
    )

    namespace = {
        "_OFFSET_KEYS": (
            "TEMP_OFFSET",
            "HUM_OFFSET",
            "OUTSIDE_TEMP_OFFSET",
            "OUTSIDE_HUM_OFFSET",
        ),
        "_RETIRED_SOURCE_IDS": {"mqtt:ds18b20", "mqtt:dht22"},
        "math": math,
        "reset_vpd_control": lambda runtime=None, reason="": None,
    }
    exec(
        compile(
            ast.Module(body=functions, type_ignores=[]),
            filename=str(SENSORS_PATH),
            mode="exec",
        ),
        namespace,
    )
    return namespace


class FakeState:
    def __init__(self):
        self.live_state = {}


class FakeRuntime:
    def __init__(self, assignments):
        self.tent_id = "tent_optional_ppfd"
        self.config = {
            "SENSOR_ASSIGNMENTS": dict(assignments),
            "TEMP_OFFSET": 0.0,
            "HUM_OFFSET": 0.0,
            "OUTSIDE_TEMP_OFFSET": 0.0,
            "OUTSIDE_HUM_OFFSET": 0.0,
        }
        self.state = FakeState()
        self.state_lock = threading.Lock()
        self.persist_calls = 0

    def persist_config(self):
        self.persist_calls += 1


def assignment(source_id, field):
    return {
        "source_id": source_id,
        "field": field,
        "label": source_id,
    }


def main():
    namespace = load_assignment_functions()
    save_assignments = namespace["_save_assignments"]

    namespace["_source_map"] = lambda: {
        "climate:inside": {
            "id": "climate:inside",
            "label": "Klimasensor innen",
            "type": "mqtt",
            "temperature": 24.2,
            "humidity": 61.0,
        },
        "light:only": {
            "id": "light:only",
            "label": "Lichtsensor",
            "type": "hardware",
            "ppfd": 450,
        },
    }
    options = namespace["_sensor_options"]()
    require(
        options["outside_temperature"] == options["temperature"]
        and options["outside_humidity"] == options["humidity"],
        "Sensor-API bietet Außen-Temperatur und Außen-Feuchte als eigene Auswahllisten",
    )
    require(
        options["outside_temperature"][0]["field"] == "temperature"
        and options["outside_humidity"][0]["field"] == "humidity",
        "Außenauswahl verwendet weiterhin die physisch korrekten Sensorfelder",
    )

    apply_calls = []
    reset_calls = []

    def apply_sensor_assignments(runtime=None):
        apply_calls.append(runtime)
        runtime.state.live_state["sensor_assignments"] = dict(
            runtime.config.get("SENSOR_ASSIGNMENTS", {})
        )
        return True

    namespace["apply_sensor_assignments"] = apply_sensor_assignments
    namespace["reset_vpd_control"] = lambda runtime=None, reason="": reset_calls.append(
        (runtime, reason)
    )

    runtime = FakeRuntime({
        "temperature": assignment("old:temp", "temperature"),
        "humidity": assignment("old:hum", "humidity"),
        "ppfd": assignment("old:light", "ppfd"),
    })

    result = save_assignments(runtime, {
        "temperature": assignment("new:temp", "temperature"),
        "humidity": assignment("new:hum", "humidity"),
        "ppfd": {
            "source_id": None,
            "field": None,
            "label": None,
        },
    })

    saved = runtime.config["SENSOR_ASSIGNMENTS"]
    require(
        saved["temperature"]["source_id"] == "new:temp",
        "Temperaturquelle wird trotz leerer PPFD-Auswahl gespeichert",
    )
    require(
        saved["humidity"]["source_id"] == "new:hum",
        "Feuchtequelle wird trotz leerer PPFD-Auswahl gespeichert",
    )
    require(
        "ppfd" not in saved,
        "Leere PPFD-Auswahl entfernt nur die optionale PPFD-Zuweisung",
    )
    require(
        result["success"] is True
        and runtime.persist_calls == 1
        and apply_calls == [runtime],
        "Optionale PPFD-Zuweisung wird persistiert und angewendet",
    )
    require(
        reset_calls == [(runtime, "Sensorzuweisung geändert")],
        "Neue Innenzuweisungen setzen eine laufende VPD-Wirkungsprüfung zurück",
    )

    reset_calls.clear()
    outside_runtime = FakeRuntime({
        "temperature": assignment("inside:temp", "temperature"),
        "humidity": assignment("inside:hum", "humidity"),
    })
    save_assignments(outside_runtime, {
        "outside_temperature": assignment("outside:climate", "temperature"),
        "outside_humidity": assignment("outside:climate", "humidity"),
    })
    require(
        outside_runtime.config["SENSOR_ASSIGNMENTS"]["outside_temperature"]["field"]
        == "temperature"
        and outside_runtime.config["SENSOR_ASSIGNMENTS"]["outside_humidity"]["field"]
        == "humidity",
        "Optionale Außen-Temperatur und Außen-Feuchte werden streng gespeichert",
    )
    require(
        reset_calls == [(outside_runtime, "Sensorzuweisung geändert")],
        "Eine neue Außenquelle verwirft die Wirkungshistorie der alten Quelle",
    )

    save_assignments(outside_runtime, {"outside_humidity": None})
    remaining_outside = outside_runtime.config["SENSOR_ASSIGNMENTS"]
    require(
        "outside_humidity" not in remaining_outside
        and remaining_outside["outside_temperature"]["source_id"]
        == "outside:climate",
        "Eine Außen-Zuweisung kann einzeln entfernt werden, ohne die andere zu löschen",
    )

    reset_calls.clear()
    outside_offset_result = save_assignments(outside_runtime, {
        "offsets": {
            "OUTSIDE_TEMP_OFFSET": 0.6,
            "OUTSIDE_HUM_OFFSET": -2.5,
        },
    })
    require(
        outside_runtime.config["OUTSIDE_TEMP_OFFSET"] == 0.6
        and outside_runtime.config["OUTSIDE_HUM_OFFSET"] == -2.5
        and outside_offset_result["offsets"]["OUTSIDE_TEMP_OFFSET"] == 0.6
        and outside_offset_result["offsets"]["OUTSIDE_HUM_OFFSET"] == -2.5,
        "Beide Außen-Offsets werden stationsbezogen persistiert und zurückgegeben",
    )
    require(
        outside_runtime.config["TEMP_OFFSET"] == 0.0
        and outside_runtime.config["HUM_OFFSET"] == 0.0,
        "Außenkalibrierung verändert niemals die Innen-Offsets",
    )
    require(
        reset_calls == [(outside_runtime, "Sensor-Offset geändert")],
        "Eine Außenkalibrierung startet die VPD-Wirkungsprüfung frisch",
    )

    try:
        save_assignments(outside_runtime, {
            "offsets": {"OUTSIDE_TEMP_OFFSET": float("nan")},
        })
    except ValueError as exc:
        require(
            "OUTSIDE_TEMP_OFFSET muss endlich sein" in str(exc),
            "Nicht-endliche Außen-Offsets werden sicher abgewiesen",
        )
    else:
        raise AssertionError("NaN wurde unerwartet als Außen-Offset akzeptiert")

    reset_calls.clear()
    offset_runtime = FakeRuntime({
        "temperature": assignment("inside:temp", "temperature"),
        "humidity": assignment("inside:hum", "humidity"),
    })
    save_assignments(offset_runtime, {
        "offsets": {"TEMP_OFFSET": 0.4},
    })
    require(
        offset_runtime.config["TEMP_OFFSET"] == 0.4
        and reset_calls == [(offset_runtime, "Sensor-Offset geändert")],
        "Eine geänderte Innenkalibrierung setzt die alte VPD-Wirkungshistorie zurück",
    )

    runtime = FakeRuntime({
        "temperature": assignment("old:temp", "temperature"),
        "humidity": assignment("old:hum", "humidity"),
        "ppfd": assignment("keep:light", "ppfd"),
    })
    save_assignments(runtime, {
        "temperature": assignment("partial:temp", "temperature"),
    })
    require(
        runtime.config["SENSOR_ASSIGNMENTS"]["ppfd"]["source_id"]
        == "keep:light",
        "Teilupdates ohne PPFD-Feld behalten die bestehende PPFD-Zuweisung",
    )

    runtime = FakeRuntime({})
    save_assignments(runtime, {
        "temperature": assignment("valid:temp", "temperature"),
        "humidity": assignment("valid:hum", "humidity"),
        "ppfd": assignment("valid:light", "ppfd"),
    })
    require(
        runtime.config["SENSOR_ASSIGNMENTS"]["ppfd"]["source_id"]
        == "valid:light",
        "Vorhandene PPFD-Quellen werden weiterhin streng normalisiert und gespeichert",
    )

    try:
        save_assignments(runtime, {
            "temperature": {"source_id": None},
        })
    except ValueError as exc:
        require(
            "source_id für temperature fehlt" in str(exc),
            "Temperatur bleibt eine verpflichtende, streng validierte Zuweisung",
        )
    else:
        raise AssertionError("Leere Temperaturzuweisung wurde unerwartet akzeptiert")

    ui = (ROOT / "templates/sensoren.html").read_text(encoding="utf-8")
    require(
        'id="outside-temperature-source"' in ui
        and 'id="outside-humidity-source"' in ui,
        "Offsets-&-Details-Seite besitzt manuelle Dropdowns für beide Außenwerte",
    )
    require(
        'outside_temperature: outsideTempOption' in ui
        and 'outside_humidity: outsideHumOption' in ui,
        "Gemeinsames Speichern überträgt beide manuellen Außenzuweisungen",
    )
    require(
        'outside_temperature: "Keine Außen-Temperatur zugewiesen"' in ui
        and 'outside_humidity: "Keine Außen-Luftfeuchte zugewiesen"' in ui,
        "Beide optionalen Außenquellen lassen sich im Dropdown gezielt entfernen",
    )
    require(
        "gespeichert · derzeit nicht verfügbar" in ui,
        "Vorübergehend offline Quellen bleiben beim Speichern unverändert erhalten",
    )
    require(
        "fmt(s.outside_temp)" in ui
        and "fmt(s.outside_hum)" in ui,
        "Detailseite zeigt die aktuell angewendeten Außenmesswerte",
    )
    require(
        'id="OUTSIDE_TEMP_OFFSET"' in ui
        and 'id="OUTSIDE_HUM_OFFSET"' in ui
        and "flushOffsetSave(\"OUTSIDE_TEMP_OFFSET\")" in ui
        and "flushOffsetSave(\"OUTSIDE_HUM_OFFSET\")" in ui,
        "Detailseite besitzt speicherbare Offset-Regler für beide Außenwerte",
    )
    require(
        "fmt(s.outside_temp_raw)" in ui
        and "fmt(s.outside_hum_raw)" in ui,
        "RAW- und korrigierte Außenwerte bleiben bei der Kalibrierung sichtbar",
    )

    config_source = (ROOT / "core/config.py").read_text(encoding="utf-8")
    config_update_source = (ROOT / "core/config_update.py").read_text(
        encoding="utf-8"
    )
    state_source = (ROOT / "core/state.py").read_text(encoding="utf-8")
    tent_route_source = (ROOT / "routes/tents.py").read_text(encoding="utf-8")
    require(
        '"OUTSIDE_TEMP_OFFSET": 0.0' in config_source
        and '"OUTSIDE_HUM_OFFSET": 0.0' in config_source,
        "Bestehende Stationen erhalten für beide Außen-Offsets sichere Null-Defaults",
    )
    require(
        '"outside_temp_raw": None' in state_source
        and '"outside_hum_raw": None' in state_source,
        "Runtime-State trennt RAW- und korrigierte Außenwerte",
    )
    require(
        '"OUTSIDE_TEMP_OFFSET"' in config_update_source
        and '"OUTSIDE_HUM_OFFSET"' in config_update_source
        and '"OUTSIDE_TEMP_OFFSET"' in tent_route_source
        and '"OUTSIDE_HUM_OFFSET"' in tent_route_source,
        "Außen-Offsets bleiben auf den stationsbezogenen Sensor-Endpunkt begrenzt",
    )

    print("✅ Growstar 3.16.3 / SENSOR.OUTSIDE.2 vollständig geprüft")


if __name__ == "__main__":
    main()
