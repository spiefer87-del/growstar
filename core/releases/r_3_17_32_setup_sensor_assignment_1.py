"""Growstar 3.17.32 / SETUP.SENSORS.1 release metadata."""

RELEASE = {
    "version": "3.17.32",
    "date": "2026-10-01",
    "phase": "SETUP.SENSORS.1",
    "title": "Sensorzuordnung bei den Grow-Stationen im Setup",
    "summary": "Sensorseiten zeigen Messwerte; Zuordnung per Drag-and-Drop erfolgt im Stations-Setup.",
    "changes": [
        "Sensorquellen und ihre Live-Messwerte bleiben auf der zentralen Sensorseite sichtbar.",
        "Innen-, Außen- und PPFD-Quellen werden den Grow-Stationen im Setup zugeordnet.",
        "Desktop-Drag, mobile Ziehbewegung und Antippen mit anschließender Zielwahl werden unterstützt.",
        "Die stationsbezogene Sensorseite behält Livewerte und Offset-Kalibrierung ohne doppelte Zuordnung.",
        "Die bestehende API und gespeicherte Sensorzuweisungen bleiben erhalten; keine Datenbankmigration.",
    ],
    "tests": [
        "python3 tests/regression/check_setup_sensor_assignment.py",
        "python3 tests/regression/check_sensor_ppfd_assignment_hardware.py",
        "python3 tests/regression/check_optional_ppfd_assignment.py",
        "python3 tests/regression/check_vpd_intelligent_control.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
