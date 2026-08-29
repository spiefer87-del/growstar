"""Growstar 3.15.4 / HISTORY.BINDING.FIX release metadata."""

RELEASE = {
    "version": "3.15.4",
    "date": "2026-08-29",
    "phase": "HISTORY.BINDING.FIX",
    "title": "Messwert-Historie reparieren",
    "summary": (
        "Repariert den SQLite-Bindingfehler in insert_measurement(), durch den "
        "seit der PPFD-Erweiterung keine neuen Historienpunkte geschrieben wurden."
    ),
    "changes": (
        "Fehlendes ppfd im Parameter-Tupel von insert_measurement() ergänzt.",
        "8 SQL-Spalten, 8 Platzhalter und 8 Bindings sind wieder synchron.",
        "Temperatur-, Feuchte-, VPD- und PPFD-Historie werden wieder geschrieben.",
        "Echter SQLite-Regressionstest prüft den vollständigen Insert.",
        "PPFD-Dashboard-Test wird falls nötig von JS-Zeilenumbrüchen entkoppelt.",
        "Keine Änderung an Regelung, Aktorik oder Sensorzuweisungen.",
    ),
    "tests": (
        "python3 tests/regression/check_history_binding_fix.py",
        "python3 tests/regression/check_environment_charts.py",
        "python3 tests/regression/check_spiderfarmer_ppfd_dashboard.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
