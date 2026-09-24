"""Growstar 3.17.27 / GROWCAM.TIMELAPSE-SCHEDULE.1 release metadata."""

RELEASE = {
    "version": "3.17.27",
    "date": "2026-09-24",
    "phase": "GROWCAM.TIMELAPSE-SCHEDULE.1",
    "title": "Zeitraffer-Aufnahmeplan mit fester Uhrzeit",
    "summary": "Zeitraffer-Aufnahmen können an einer gewählten Uhrzeit ausgerichtet werden; die Medienbereiche klappen einzeln auf.",
    "changes": [
        "Der Aufnahmeplan, die Videos, die Videoerstellung und das Bilderarchiv öffnen sich jeweils einzeln.",
        "Der Aktivierungszustand und der Ein-/Aus-Schalter bleiben oberhalb des Aufnahmeplans sichtbar.",
        "Eine optionale Uhrzeit verankert Intervalle an festen lokalen Uhrzeiten, etwa stündlich um Minute 15.",
        "Ohne gewählte Uhrzeit behalten bestehende Kameras ihr bisheriges Intervallverhalten.",
        "Die nächste planmäßige Zeitraffer-Aufnahme ist im Aufnahmeplan sichtbar.",
    ],
    "tests": [
        "python3 tests/regression/check_growcam_timelapse_schedule.py",
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_growcam_multi_camera.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
