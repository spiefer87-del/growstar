"""Growstar 3.15.12 / SETTINGS.VALIDATION.1 release metadata."""

RELEASE = {
    "version": "3.15.12",
    "date": "2026-09-01",
    "phase": "SETTINGS.VALIDATION.1",
    "title": "Bestehende Klima- und Alarmwerte wieder speicherbar",
    "summary": (
        "Die Klimaseite akzeptiert bestehende gültige Dezimal- und Ganzzahlwerte "
        "wieder unabhängig von einem verschobenen HTML-Schrittgitter. Echte "
        "Bereichs- und Sicherheitsfehler bleiben vollständig geschützt."
    ),
    "changes": (
        "Alarmtoleranzen besitzen kein künstliches HTML-Schrittgitter mehr.",
        "MIN_TEMP, MAX_TEMP, MIN_HUM und MAX_HUM akzeptieren vorhandene gültige Dezimalwerte.",
        "Die konkreten Altwerte 5,0 Grad, 15,1 Prozent und 80 Prozent sind wieder speicherbar.",
        "Plus/Minus behält für Temperaturalarme und Temperaturgrenzen 0,5er-Schritte.",
        "Plus/Minus behält für Feuchtealarme und Feuchtegrenzen 1er-Schritte.",
        "Die Rampendauer verwendet im Eingabefeld wie ihre Tasten jetzt 5-Minuten-Schritte.",
        "Browser-Min-/Max-Grenzen und Pflichtfeldprüfung bleiben aktiv.",
        "Die zentrale Backend-Validierung für unsichere Grenzkombinationen bleibt unverändert.",
        "Weder Profilvorlagen noch Stationswerte werden durch den Patch verändert.",
    ),
    "tests": (
        "python3 tests/regression/check_settings_numeric_compatibility.py",
        "python3 tests/regression/check_profile_draft_management.py",
        "python3 tests/regression/check_profile_current_copy.py",
        "python3 tests/regression/check_morning_ramp_profile_sync.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
