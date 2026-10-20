"""Growstar 3.17.49 / SETTINGS.MODE.DROPDOWN.1."""

RELEASE = {
    "version": "3.17.49",
    "date": "2026-10-20",
    "phase": "SETTINGS.MODE.DROPDOWN.1",
    "title": "Betriebsart direkt im Regelbereich auswählen",
    "summary": "Das VPD-Betriebsart-Dropdown steht unter den Ansichtsreitern; der gespeicherte Modus ist sofort sichtbar.",
    "changes": [
        "Klassisch- und VPD-Reiter bleiben unverändert als Ansichtsumschaltung erhalten.",
        "Das vorhandene Dropdown für Aus, Beobachten und Automatisch wandert aus dem VPD-Klappmenü in den Regelbereich.",
        "Zwei wenig hilfreiche Statuskacheln weichen einer Zeile mit dem tatsächlich gespeicherten Modus.",
        "Ein ausgewählter Modus wird weiterhin erst mit Einstellungen speichern übernommen.",
    ],
    "tests": [
        "python3 tests/regression/check_vpd_ui_cleanup.py",
        "python3 tests/regression/check_profile_settings_accordion.py",
        "python3 tests/regression/check_profile_draft_management.py",
        "python3 tests/regression/check_vpd_intelligent_control.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
