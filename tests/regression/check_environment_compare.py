#!/usr/bin/env python3
"""All climate series share station/time but keep their native units."""

import sqlite3
import sys
import tempfile
import time
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import db

if "flask" not in sys.modules:
    flask = types.ModuleType("flask")
    flask.jsonify = lambda *args, **kwargs: args[0] if args else kwargs
    flask.request = types.SimpleNamespace(args={})
    flask.send_file = lambda *args, **kwargs: None
    sys.modules["flask"] = flask
from routes import diagrams


def require(condition, message):
    assert condition, message
    print("✅", message)


def main():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "data.db"
        connect = sqlite3.connect
        with connect(path) as connection:
            connection.execute("""CREATE TABLE temp_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, tent_id TEXT, ts INTEGER,
                temp REAL, temp_target REAL, hum REAL, hum_target REAL,
                vpd REAL, ppfd REAL, water_temp REAL)""")
            connection.execute(
                "INSERT INTO temp_history(tent_id, ts, temp, water_temp) VALUES (?, ?, ?, ?)",
                ("tent_1", int(time.time()) - 100, 25.1, 20.4),
            )
        old_file = db.DB_FILE
        db.DB_FILE = str(path)
        try:
            db.init_db()
            with connect(path) as connection:
                fields = {row[1] for row in connection.execute("PRAGMA table_info(temp_history)")}
            require({"outside_temp", "outside_hum"} <= fields,
                    "Vorhandene Datenbanken erhalten beide Außenspalten")
            db.insert_measurement(25.5, 26, hum=55, vpd=1.4, ppfd=350,
                                  water_temp=21.2, outside_temp=19.4,
                                  outside_hum=66, tent_id="tent_1")
            db.insert_measurement(30, 29, water_temp=24, outside_temp=22,
                                  tent_id="tent_2")
            with patch.object(diagrams.sqlite3, "connect", side_effect=lambda *_: connect(path)):
                first = diagrams._history_rows("tent_1", "1h", "all")
                second = diagrams._history_rows("tent_2", "1h", "all")
            require(len(first) == 2 and len(second) == 1,
                    "Vergleich trennt Stationen und behält frühere Messungen")
            require(first[0]["temp"] == 25.1 and first[0]["water_temp"] == 20.4 and
                    first[0]["outside_temp"] is None,
                    "Vor dem Update unbekannte Außenwerte bleiben Datenlücken")
            require(first[1]["water_temp"] == 21.2 and first[1]["outside_temp"] == 19.4 and
                    first[1]["outside_hum"] == 66 and first[1]["ppfd"] == 350,
                    "Ein Messzeitpunkt liefert Innen-, Wasser- und Außenwerte zusammen")
            now = int(time.time())
            with connect(path) as connection:
                connection.executemany(
                    "INSERT INTO temp_history(tent_id, ts, temp) VALUES (?, ?, ?)",
                    [("tent_1", now - 36 * 3600, 22),
                     ("tent_1", now - 20 * 24 * 3600, 23),
                     ("tent_1", now - 31 * 24 * 3600, 24)],
                )
            with patch.object(diagrams.sqlite3, "connect", side_effect=lambda *_: connect(path)):
                range_48h = diagrams._history_rows("tent_1", "48h", "temp")
                range_30d = diagrams._history_rows("tent_1", "30d", "all")
            require(any(row["temp"] == 22 for row in range_48h) and
                    not any(row["temp"] == 23 for row in range_48h),
                    "48 Stunden enthalten Messungen von gestern, aber keine älteren")
            require(any(row["temp"] == 23 for row in range_30d) and
                    not any(row["temp"] == 24 for row in range_30d),
                    "30 Tage schließen ältere Messungen aus")
        finally:
            db.DB_FILE = old_file

    chart = (ROOT / "templates/environment_history.html").read_text()
    tile = (ROOT / "templates/grow_control.html").read_text()
    require('id="compare-picker"' in chart and 'data-metric="compare"' in chart and
            'growstar-chart-series:${TENT_ID}' in chart,
            "Kurvenwahl ist aufklappbar und pro Station gespeichert")
    require('water_temp:{label:"Wasser",group:"temp"' in chart and
            'outside_temp:{label:"Außen",group:"temp"' in chart and
            'temp:{label:"Zelt",group:"temp"' in chart,
            "Drei Temperaturkurven teilen dieselbe Celsius-Skala")
    require('hum:{title:"Luftfeuchtigkeit' in chart and
            'vpd:{title:"VPD' in chart and 'ppfd:{title:"Licht' in chart and
            'spanGaps:false' in chart,
            "Weitere Einheiten behalten eigene Werte und Datenlücken bleiben sichtbar")
    require('type=all' in chart and 'grow_control_tent_compare' in tile,
            "Wassertemperatur-Kachel öffnet direkt den Stationsvergleich")
    require('data-range="48h"' in chart and 'data-range="30d"' in chart,
            "48 Stunden und 30 Tage sind in der Zeitraumwahl vorhanden")
    dashboard = (ROOT / "routes/dashboard.py").read_text()
    require('data-metric="live"' in chart and 'data-metric="compare"' in chart and
            'id="history-card"' in chart and 'id="live-panel"' in chart and
            '@app.route("/grow-control/tents/<tent_id>/live-chart")' in dashboard,
            "Live besitzt einen eigenen Reiter, eine eigene URL und eine getrennte Ansicht")
    print("✅ ENV.CHART.COMPARE.1 erfolgreich")


if __name__ == "__main__":
    main()
