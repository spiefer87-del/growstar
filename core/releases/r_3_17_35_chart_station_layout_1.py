"""Growstar 3.17.35 / ENV.STATION.LAYOUT.1 release metadata."""

RELEASE = {
    "version": "3.17.35",
    "date": "2026-10-01",
    "phase": "ENV.STATION.LAYOUT.1",
    "title": "Stationswechsel im Diagramm dauerhaft rechts",
    "summary": "Feste rechte Spalte für die Stationsauswahl in Zeitverläufen und VPD-Karte.",
    "changes": [
        "Zeitraum und Stationsauswahl stehen in einer festen gemeinsamen Zeile.",
        "Sollwert- und Zusatzkurven-Schalter stehen darunter und verschieben die Stationsauswahl nicht.",
        "Auf schmalen Displays kann nur die Zeitbereichsleiste seitlich gescrollt werden.",
        "Die VPD-Karte verwendet dieselbe Stationsposition.",
        "Keine Änderung an Sensordaten, Verlaufsberechnung oder Regelung.",
    ],
    "tests": [
        "python3 tests/regression/check_chart_station_switch_layout.py",
        "python3 tests/regression/check_combined_climate_chart.py",
        "python3 tests/regression/check_environment_charts.py",
        "python3 tests/regression/check_chart_stability.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
