"""Growstar 3.17.0 / INTELLIGENCE.EVENTS.1 release metadata."""

RELEASE = {
    "version": "3.17.0",
    "date": "2026-09-11",
    "phase": "INTELLIGENCE.EVENTS.1",
    "title": "Grow Intelligence Ereignis-Timeline",
    "summary": (
        "Growstar startet das Kapitel 3.17 mit einem zentralen, lokalen "
        "Ereignisspeicher und einer stationsbezogenen, schreibgeschützten Timeline."
    ),
    "changes": [
        "Neuer additiver SQLite-Ereignisspeicher mit Deduplizierung und Metadaten.",
        "Stations-, Zeitraum-, Kategorie- und Prioritätsfilter in Grow Control.",
        "Kennzahlen und chronologische Tagesgruppen schaffen eine gemeinsame Betriebssicht.",
        "Grow Intelligence ist über Hauptmenü und Grow-Control-Dashboard erreichbar.",
        "Die erste Ausbaustufe verändert weder Regelung noch Hardwarezustände.",
    ],
    "tests": [
        "python3 tests/regression/check_grow_intelligence_events.py",
        "python3 tests/regression/check_grow_control_quick_menu.py",
        "python3 tests/regression/check_app_shell_navigation.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
