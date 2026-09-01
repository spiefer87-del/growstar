"""Growstar 3.15.10 / PROFILE.MANAGEMENT.2 release metadata."""

RELEASE = {
    "version": "3.15.10",
    "date": "2026-09-01",
    "phase": "PROFILE.MANAGEMENT.2",
    "title": "Stationswerte kopieren und Sonnenverlauf profilieren",
    "summary": (
        "Die Dashboard-Profilkarte führt wieder über Klima & Grenzwerte. "
        "Aktuelle Stationswerte können als Profilentwurf übernommen werden; "
        "Temperaturrampe und Sonnenverlauf gehören vollständig zur Vorlage."
    ),
    "changes": (
        "Die Profilkarte im Zelt-Dashboard öffnet zuerst Klima & Grenzwerte.",
        "Die Klimaseite bleibt der eindeutige Einstieg zur getrennten Profilverwaltung.",
        "Aktuelle gespeicherte Stationswerte lassen sich in das gerade ausgewählte Profil kopieren.",
        "Die Kopie bleibt ein Browserentwurf und verändert weder Vorlage noch Runtime automatisch.",
        "Erst Profil speichern persistiert den kopierten Entwurf im controllerweiten Katalog.",
        "Temperatur-Rampe, Rampendauer und Tag-/Nachtzeiten werden vollständig mitkopiert.",
        "Sonnenverlauf EIN/AUS, Aufgang, Untergang und Start-/Endleistung sind profilbezogen editierbar.",
        "Alte Profile erhalten kompatible sichere Sonnenverlauf-Standardwerte, ohne Schreibzugriff beim Laden.",
        "Ein Sonnenprofil darf auch ohne aktuelle Hardware vorbereitet und gespeichert werden.",
        "Die Aktivierung eines aktiven Sonnenverlaufs bleibt ohne geeigneten Lichtcontroller serverseitig gesperrt.",
        "Eine blockierte Profilaktivierung verändert weder Stationsconfig noch Rampenzustand.",
        "Die mobile Aktionskarte ist nicht mehr sticky und verdeckt dadurch keine Profilfelder.",
    ),
    "tests": (
        "python3 tests/regression/check_profile_current_copy.py",
        "python3 tests/regression/check_profile_draft_management.py",
        "python3 tests/regression/check_light_sunrise_sunset.py",
        "python3 tests/regression/check_light_sun_controller_guard.py",
        "python3 tests/regression/check_light_sun_controller_guard_2.py",
        "python3 tests/regression/check_morning_ramp_profile_sync.py",
        "python3 tests/regression/check_capability_routing.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
