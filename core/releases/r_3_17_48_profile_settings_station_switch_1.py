"""Growstar 3.17.48 / PROFILE.SETTINGS.STATION.SWITCH.1."""

RELEASE = {
    "version": "3.17.48",
    "date": "2026-10-20",
    "phase": "PROFILE.SETTINGS.STATION.SWITCH.1",
    "title": "Stationswechsel und aufgeräumte Profil-Setup-Seiten",
    "summary": "Klima und Profile zeigen den Stationsschalter oben rechts; Profilverwaltung steht bei den Speicheraktionen.",
    "changes": [
        "Klima & Grenzwerte bietet einen mobilen Stationswechsel mit Schutz ungespeicherter Einstellungen.",
        "Die Profilseite zeigt ihren vorhandenen Stationswechsel an derselben Position.",
        "Profile verwalten wandert von der Klima-Kopfzeile zu den Speicheraktionen.",
        "Überflüssige Erklärungstexte im oberen Bereich entfallen.",
    ],
    "tests": [
        "python3 tests/regression/check_profile_draft_management.py",
        "python3 tests/regression/check_profile_current_copy.py",
        "python3 tests/regression/check_profile_settings_accordion.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
