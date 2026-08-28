"""Growstar 3.14.2 / LIGHT.SUN.GUARD.2 release metadata."""

RELEASE = {
    "version": "3.14.2",
    "date": "2026-08-28",
    "phase": "LIGHT.SUN.GUARD.2",
    "title": "Frontend-Reparatur für Lichtcontroller-Sperre",
    "summary": (
        "Repariert den unvollständig angewendeten Frontend-Teil des "
        "Sonnenverlauf-Guards. Ohne Licht-Controller wird die Karte nun "
        "sichtbar ausgegraut und vollständig deaktiviert."
    ),
    "changes": (
        "Fehlendes feature-unavailable CSS ergänzt.",
        "Fehlende applyLightSunAvailability-Funktion ergänzt.",
        "Sonnenverlauf-Felder und Plus/Minus werden ohne Licht-Controller deaktiviert.",
        "Hinweistext erklärt, warum die Funktion nicht verfügbar ist.",
        "Persistiertes LIGHT_SUN_ENABLED kann die UI ohne Controller nicht reaktivieren.",
        "Save-Payload sendet ohne Controller niemals LIGHT_SUN_ENABLED=1.",
        "Backend-Guard und funktionierende Rampenlogik bleiben unverändert.",
    ),
    "tests": (
        "python3 tests/regression/check_light_sun_controller_guard_2.py",
        "python3 tests/regression/check_light_sunrise_sunset.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
