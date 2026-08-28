"""Growstar 3.14.1 / LIGHT.SUN.GUARD.1 release metadata."""

RELEASE = {
    "version": "3.14.1",
    "date": "2026-08-28",
    "phase": "LIGHT.SUN.GUARD.1",
    "title": "Sonnenverlauf nur mit Licht-Controller",
    "summary": "Sonnenaufgang/Sonnenuntergang ist ohne zugewiesenen Licht-Controller deaktiviert.",
    "changes": (
        "Profilseite graut den Sonnenverlauf ohne Licht-Controller aus.",
        "Eingaben und Plus/Minus werden deaktiviert.",
        "Eine sichtbare Erklärung nennt die fehlende Controller-Zuweisung.",
        "Config-API blockiert Aktivierung ohne Controller.",
        "Runtime fällt bei später entfernter Zuordnung auf normales ENV-Licht zurück.",
    ),
    "tests": (
        "python3 tests/regression/check_light_sun_controller_guard.py",
        "python3 tests/regression/check_light_sunrise_sunset.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
