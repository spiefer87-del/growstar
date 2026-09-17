"""Growstar 3.17.22 / PROFILE-SETTINGS.STATION-SWITCHER.1 release metadata."""

RELEASE = {
    "version": "3.17.22",
    "date": "2026-09-17",
    "phase": "PROFILE-SETTINGS.STATION-SWITCHER.1",
    "title": "Einheitlicher kompakter Stationswechsel",
    "summary": (
        "Profilverwaltung und Klima & Grenzwerte verwenden denselben kompakten "
        "Stationsumschalter wie das Grow-Control-Dashboard."
    ),
    "changes": [
        "Der große Stationsrahmen der Profilverwaltung wurde durch eine kompakte Auswahl ersetzt.",
        "Klima & Grenzwerte kann nun direkt zwischen Zelt 1 und Zelt 2 wechseln.",
        "Die native Stationsauswahl zeigt LIVE, SHADOW, BEREIT oder OFFLINE.",
        "Der Wechsel bleibt im aktuellen Arbeitsbereich der ausgewählten Station.",
        "Nicht geladene Stationen bleiben gesperrt.",
        "Ungespeicherte Profil- und Klimaentwürfe werden vor dem Wechsel geschützt.",
    ],
    "tests": [
        "python3 tests/regression/check_profile_settings_station_switcher.py",
        "python3 tests/regression/check_profile_station_switcher.py",
        "python3 tests/regression/check_profile_settings_accordion.py",
        "python3 tests/regression/check_profile_activation_ui.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
