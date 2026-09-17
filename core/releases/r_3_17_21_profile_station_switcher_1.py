"""Growstar 3.17.21 / PROFILE.STATION-SWITCHER.1 release metadata."""

RELEASE = {
    "version": "3.17.21",
    "date": "2026-09-14",
    "phase": "PROFILE.STATION-SWITCHER.1",
    "title": "Stationswechsel in der Profilverwaltung",
    "summary": (
        "Die Profilverwaltung wechselt direkt zwischen allen geladenen "
        "Grow-Stationen und behält dabei den aktuellen Arbeitsbereich bei."
    ),
    "changes": [
        "Oberhalb der Profilauswahl steht ein Stationsumschalter wie im Grow-Control-Dashboard.",
        "Stationsname und Laufzeitmodus LIVE, SHADOW, BEREIT oder OFFLINE werden gemeinsam angezeigt.",
        "Nach der Auswahl öffnet Growstar direkt die Profilverwaltung der gewählten Station.",
        "Aktives Profil, Controller-Verfügbarkeit und Stationswerte werden anschließend stationsbezogen neu geladen.",
        "Nicht geladene Stationen sind nicht auswählbar.",
        "Ungespeicherte Profiländerungen werden vor dem Stationswechsel ausdrücklich geschützt.",
    ],
    "tests": [
        "python3 tests/regression/check_profile_station_switcher.py",
        "python3 tests/regression/check_profile_activation_ui.py",
        "python3 tests/regression/check_profile_settings_accordion.py",
        "python3 tests/regression/check_profile_draft_management.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
