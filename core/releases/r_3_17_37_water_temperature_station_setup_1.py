"""Growstar 3.17.37 / WATER.TEMP.SETUP.1."""

RELEASE = {
    "version": "3.17.37",
    "date": "2026-10-02",
    "phase": "WATER.TEMP.SETUP.1",
    "title": "Wassertemperatur pro Grow-Station zuweisen und anzeigen",
    "summary": "Stationsauswahl im Setup und Wassertemperatur mit eigenem Verlauf.",
    "changes": [
        "Grow Station Setup zeigt jeweils eine Station mit Umschalter.",
        "Optionaler Wassertemperatursensor nutzt eine frische Temperaturquelle der gewählten Station.",
        "Wassertemperatur erhält einen eigenen stationsbezogenen Verlauf und eine Dashboard-Kachel.",
        "Historische Daten bleiben erhalten; die neue Datenbankspalte wird beim Start ergänzt.",
    ],
    "tests": [
        "python3 tests/regression/check_water_temperature_station_setup.py",
        "python3 tests/regression/check_setup_sensor_assignment.py",
        "python3 tests/regression/check_history_binding_fix.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
