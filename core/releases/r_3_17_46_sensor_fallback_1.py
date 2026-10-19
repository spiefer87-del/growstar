"""Growstar 3.17.46 / SENSOR.FALLBACK.1."""

RELEASE = {
    "version": "3.17.46",
    "date": "2026-10-19",
    "phase": "SENSOR.FALLBACK.1",
    "title": "Fallback-Sensoren je Station und Messwert",
    "summary": "Ein zweiter Sensor übernimmt bei fehlenden, ungültigen oder veralteten Primärwerten.",
    "changes": [
        "Grow Station Setup bietet für jeden zugewiesenen Messwert einen optionalen zweiten Sensor.",
        "Die Runtime prüft 120-Sekunden-Frische und Plausibilität und wechselt automatisch zurück zum Primärsensor.",
        "Bei Ausfall beider Quellen werden Innenwerte sofort als stale markiert und nicht weiter geregelt.",
        "Die aktive Fallback-Quelle wird im Setup und im Stationsstatus kenntlich gemacht.",
    ],
    "tests": [
        "python3 tests/regression/check_sensor_fallback.py",
        "python3 tests/regression/check_setup_sensor_assignment.py",
        "python3 tests/regression/check_water_temperature_station_setup.py",
        "python3 tests/regression/check_optional_ppfd_assignment.py",
        "python3 tests/regression/check_spiderfarmer_restart_sensor_continuity.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
