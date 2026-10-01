"""Growstar 3.17.31 / VPD-CHART.1 release metadata."""

RELEASE = {
    "version": "3.17.31",
    "date": "2026-09-30",
    "phase": "VPD-CHART.1",
    "title": "VPD-Klimakarte und Außentemperatur im Dashboard",
    "summary": "Stationsbezogene VPD-Chart mit Innenverlauf, Livepunkten und gut sichtbarer Außentemperatur.",
    "changes": [
        "Neue VPD-Chart pro Station: Luftfeuchte gegen Temperatur mit farbigen VPD-Zonen.",
        "Innenverlauf über 45 Minuten, sechs oder 24 Stunden; Livepunkte innen und bei vollständigen Außenwerten auch außen.",
        "Aktuelles Stationsziel erscheint als gestrichelte VPD-Linie, die bisherige VPD-Zeitreihe bleibt erreichbar.",
        "Außentemperatur mit Sensorquelle erscheint auf der Zeltseite und in der Grow-Control-Übersicht.",
        "Bei fehlendem oder veraltetem Außenwert erscheint ein klarer Leerzustand; es werden keine Werte geschätzt.",
        "Keine Änderung an VPD-Regelung, Sensorzuweisung oder Datenbankschema.",
    ],
    "tests": [
        "python3 tests/regression/check_vpd_chart.py",
        "python3 tests/regression/check_environment_charts.py",
        "python3 tests/regression/check_chart_stability.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
