"""Growstar 3.17.33 / SETUP.SENSORS.2 release metadata."""

RELEASE = {
    "version": "3.17.33",
    "date": "2026-10-01",
    "phase": "SETUP.SENSORS.2",
    "title": "Sensorzuordnung über Auswahlfelder im Stations-Setup",
    "summary": "Mobile Sensorzuordnung ohne Drag-and-Drop und ohne zusätzliche Quellliste.",
    "changes": [
        "Jede Station zeigt direkt bei Temperatur, Feuchte, PPFD und Außenklima ein natives Auswahlfeld.",
        "Nach der Auswahl wird die stationsbezogene Zuordnung sofort gespeichert und der LIVE-Preflight aktualisiert.",
        "Optionale Quellen lassen sich mit Nicht zugewiesen entfernen; Pflichtquellen bleiben geschützt.",
        "Gespeicherte Quellen bleiben sichtbar, auch wenn sie vorübergehend nicht angeboten werden.",
        "Die obere Sensorliste und alle Drag-and-Drop-Gesten entfallen im Setup.",
        "Keine Änderung an Sensor-API, Kalibrierung oder bestehenden Zuweisungen.",
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
