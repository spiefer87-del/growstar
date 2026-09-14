"""Growstar 3.17.19 / PROFILE.ACTIVATION-EVENT.1 release metadata."""

RELEASE = {
    "version": "3.17.19",
    "date": "2026-09-14",
    "phase": "PROFILE.ACTIVATION-EVENT.1",
    "title": "Profilaktivierung startet zuverlässig",
    "summary": (
        "Der Aktivierungsbutton verwendet einen registrierten Ereignis-Handler "
        "und startet ohne mobilen Browser-Bestätigungsdialog."
    ),
    "changes": [
        "Der Profil-Aktivierungsbutton ist nicht mehr von einem Inline-onclick abhängig.",
        "Die Aktion wird nach dem Laden der Seite ausdrücklich als Click-Handler registriert.",
        "Die bewusste Kombination aus Profilauswahl und separatem Aktivierungsbutton ersetzt den störanfälligen nativen Browserdialog.",
        "Nach dem Antippen zeigt die Seite sofort, welches Profil gerade aktiviert wird.",
        "Erfolg wird weiterhin erst nach der eindeutigen active_profile-Bestätigung des Backends angezeigt.",
    ],
    "tests": [
        "python3 tests/regression/check_profile_activation_ui.py",
        "python3 tests/regression/check_profile_settings_accordion.py",
        "python3 tests/regression/check_profile_draft_management.py",
        "python3 tests/regression/check_profile_current_copy.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
