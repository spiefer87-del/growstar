"""Growstar 3.17.3 / INTERVAL.NIGHT.2 release metadata."""

RELEASE = {
    "version": "3.17.3",
    "date": "2026-09-12",
    "phase": "INTERVAL.NIGHT.2",
    "title": "Vollständige Tag-/Nachtprofile für Intervallgeräte",
    "summary": (
        "Bei aktivierter Profiltrennung besitzen Tag und Nacht jeweils zwei "
        "vollständig eigenständige Intervallphasen inklusive Dauer und Shelly-Power."
    ),
    "changes": [
        "Nachtphase A und B erhalten jeweils eigene Dauer und eigene Shelly-Power.",
        "Controllerstufe und Oszillation bleiben ebenfalls pro Nachtphase einstellbar.",
        "Eine Nachtphase kann vollständig ausgeschaltet werden, ohne die Tagphase zu ändern.",
        "Aktivierte Profiltrennung hebt Tag- und Nachtbereiche farblich hervor.",
        "Die Bedienoberfläche zeigt die stationsbezogenen Tag- und Nachtzeitfenster.",
        "Bei deaktivierter Profiltrennung bleibt das Intervall rund um die Uhr profilunabhängig.",
    ],
    "tests": [
        "python3 tests/regression/check_interval_day_night.py",
        "python3 tests/regression/check_controller_states.py",
        "python3 tests/regression/check_controller_interval_ui.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
