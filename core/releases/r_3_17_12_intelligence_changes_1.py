"""Growstar 3.17.12 / INTELLIGENCE.CHANGES.1 release metadata."""

RELEASE = {
    "version": "3.17.12",
    "date": "2026-09-12",
    "phase": "INTELLIGENCE.CHANGES.1",
    "title": "Nachvollziehbare Einstellungsänderungen",
    "summary": (
        "Kleine Klima-, Profil- und VPD-Änderungen erscheinen mit ihren "
        "tatsächlichen Vorher-/Nachher-Werten in Grow Intelligence."
    ),
    "changes": [
        "Der normale Stations- und Klima-Speicherpfad ist jetzt an Grow Intelligence angebunden.",
        "Profilvorlagen zeigen die konkret veränderten Werte statt nur die Anzahl gespeicherter Felder.",
        "Ein Speichervorgang erzeugt genau ein kompaktes Ereignis mit bis zu mehreren Änderungen.",
        "Umwelt- und Profilwerte werden in der Timeline passend als Klima-Ereignisse einsortiert.",
        "Temperaturen, Feuchte, Uhrzeiten, VPD-Werte, Rampen und Sonnenverlauf werden lesbar formatiert.",
        "Unverändertes Speichern erzeugt kein Ereignis; unbekannte oder geheime Felder werden nicht protokolliert.",
        "Der technische 3.17.0-Aktivierungseintrag wird ohne Datenlöschung aus der Benutzer-Timeline ausgeblendet.",
    ],
    "tests": [
        "python3 tests/regression/check_grow_intelligence_setting_changes.py",
        "python3 tests/regression/check_grow_intelligence_noise_filter.py",
        "python3 tests/regression/check_grow_intelligence_insights.py",
        "python3 tests/regression/check_grow_intelligence_events.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
