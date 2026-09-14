"""Growstar 3.17.18 / PROFILE.ACTIVATION-UI.1 release metadata."""

RELEASE = {
    "version": "3.17.18",
    "date": "2026-09-14",
    "phase": "PROFILE.ACTIVATION-UI.1",
    "title": "Zuverlässige Profilaktivierung",
    "summary": (
        "Profilauswahl, Status und Aktivierung stehen zusammen im oberen Bereich; "
        "die Oberfläche akzeptiert nur eine eindeutig bestätigte Aktivierung."
    ),
    "changes": [
        "Der Aktivierungsbutton steht direkt unter aktivem und bearbeitetem Profil und ist mobil ohne langes Suchen erreichbar.",
        "Status- und Fehlermeldungen erscheinen unmittelbar bei der Profilauswahl.",
        "Beim Wechsel mit ungespeicherten Änderungen fragt Growstar verständlich nach, statt die Auswahl scheinbar wirkungslos zu blockieren.",
        "Ein abgebrochener Profilwechsel bewahrt den bisherigen Entwurf vollständig.",
        "Nach der Aktivierung wird Erfolg nur angezeigt, wenn das Backend exakt das angeforderte Profil als aktiv bestätigt.",
        "Die aktive Markierung und die Stationsanzeige werden erst nach dieser Bestätigung aktualisiert.",
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
