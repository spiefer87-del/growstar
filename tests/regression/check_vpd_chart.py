#!/usr/bin/env python3
"""VPD chart history isolation, live outside source and UI wiring."""

from pathlib import Path
from unittest.mock import patch
import sqlite3
import sys
import tempfile
import types

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "flask" not in sys.modules:
    flask = types.ModuleType("flask")
    flask.jsonify = lambda *args, **kwargs: args[0] if args else kwargs
    flask.request = types.SimpleNamespace(args={})
    flask.send_file = lambda *args, **kwargs: None
    sys.modules["flask"] = flask

from routes.diagrams import _history_rows
from core.helpers import calculate_vpd


def require(condition, message):
    assert condition, message
    print("✅", message)


def main():
    with tempfile.TemporaryDirectory(prefix="growstar-vpd-chart-") as directory:
        file = Path(directory) / "data.db"
        original_connect = sqlite3.connect
        with original_connect(file) as db:
            db.execute("CREATE TABLE temp_history(tent_id TEXT, ts INTEGER, temp REAL, hum REAL, vpd REAL)")
            db.executemany("INSERT INTO temp_history VALUES(?,?,?,?,?)", [
                ("tent_1", 1000, 24.1, 55.0, calculate_vpd(24.1, 55)),
                ("tent_1", 1100, 24.3, None, None),
                ("tent_1", 1200, 25.0, 58.0, calculate_vpd(25, 58)),
                ("tent_2", 1200, 29.0, 50.0, calculate_vpd(29, 50)),
            ])
        with patch("routes.diagrams.sqlite3.connect", side_effect=lambda *_: original_connect(file)), patch("routes.diagrams.time.time", return_value=1300):
            one = _history_rows("tent_1", "45m", "vpd_chart")
            two = _history_rows("tent_2", "45m", "vpd_chart")
            require([(row["temp"], row["hum"]) for row in one] == [(24.1, 55.0), (25.0, 58.0)]
                    and len(two) == 1 and two[0]["temp"] == 29.0,
                    "Chart liest nur vollständige Temperatur-Feuchte-Paare der gewählten Station")
            require(one[0]["vpd"] == calculate_vpd(24.1, 55),
                    "Historische VPD-Werte bleiben am Messpunkt")

    chart = (ROOT / "templates/vpd_chart.html").read_text()
    station = (ROOT / "templates/grow_control.html").read_text()
    hub = (ROOT / "templates/grow_control_dashboard.html").read_text()
    endpoints = (ROOT / "routes/dashboard.py").read_text()
    api = (ROOT / "routes/tents.py").read_text()
    require("grow_control_tent_vpd_chart" in endpoints and "grow_control_tent_vpd_chart" in station,
            "VPD-Chart ist pro Station aus der Zeltansicht erreichbar")
    require("grow_control_tent_vpd_chart" in (ROOT / "templates/grow_control_diagrams.html").read_text(),
            "Diagrammübersicht führt zur neuen Chart")
    require("outside_temp_source" in chart and "outside_hum" in chart and "outside_temp" in station,
            "Außentemperatur ist sichtbar; Außen-VPD benötigt zusätzlich frische Feuchte")
    require("item[\"outside_temp\"]" in api and "tent-outside" in hub,
            "Grow-Control-Übersicht zeigt frische Außentemperatur je Zelt")
    require("classic_vpd_target" in chart and "vpd_control" in chart
            and "calculate_vpd" in (ROOT / "core/helpers.py").read_text(),
            "Chart zeigt Stationsziel und verwendet die bestehende VPD-Formel")
    print("✅ VPD-CHART.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
