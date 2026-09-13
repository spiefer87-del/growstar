"""Growstar 3.17.15 / UI.TEMPERATURE-RAMP.1 release metadata."""

RELEASE = {
    "version": "3.17.15",
    "date": "2026-09-13",
    "phase": "UI.TEMPERATURE-RAMP.1",
    "title": "Temperaturrampe als eigene Kategorie",
    "summary": (
        "Die Temperaturrampe ist in Profilverwaltung und Klimaeinstellungen "
        "ein einheitliches Klappmenü zwischen Luftfeuchtigkeit und Sonnenverlauf."
    ),
    "changes": [
        "Die Temperaturrampe ist in der Profilverwaltung wieder vollständig sichtbar und bearbeitbar.",
        "Auf beiden Seiten steht sie direkt unter Luftfeuchtigkeit und über Sonnenverlauf.",
        "Die Rampe verwendet dasselbe Klappverhalten und Layout wie die übrigen Kategorien.",
        "Die Rampeneinstellungen bleiben sowohl in klassischer als auch in intelligenter VPD-Ansicht verfügbar.",
        "Dynamische Rampenbezeichnungen entfernen nicht länger den Pfeil des Klappmenüs.",
        "Speicher-, Vorschau- und Validierungslogik der bestehenden Rampe bleiben erhalten.",
    ],
    "tests": [
        "python3 tests/regression/check_profile_settings_accordion.py",
        "python3 tests/regression/check_profile_draft_management.py",
        "python3 tests/regression/check_profile_current_copy.py",
        "python3 tests/regression/check_settings_numeric_compatibility.py",
        "python3 tests/regression/check_vpd_auto_ui_lock.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
