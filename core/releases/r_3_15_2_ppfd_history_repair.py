"""Growstar 3.15.2 / PPFD.HISTORY.REPAIR release metadata."""

RELEASE = {
    "version": "3.15.2",
    "date": "2026-08-29",
    "phase": "PPFD.HISTORY.REPAIR",
    "title": "PPFD Runtime-/Historienpfad reparieren und Diagramm-Stationswechsel",
    "summary": "PPFD wird stationsbezogen in den Runtime-State projiziert; Dashboard und Historie verwenden denselben Wert.",
    "changes": (
        "PPFD-Zuweisung wird im Sensor-Assignment-Zyklus angewendet.",
        "Migrationsfallback auf bestehende Spider-Farmer Temp/Hum-Zuweisung.",
        "Stale PPFD-Werte werden nicht weitergereicht.",
        "DB-Logger erhält den stationsbezogenen light_ppfd-Wert.",
        "Dashboard-Helligkeitswert wird wieder live aktualisiert.",
        "Helligkeits-Kachel wird ohne HTML-Regex klickbar gemacht.",
        "Geräte-Dashboard erhält Struktur-Regressionstests.",
        "Diagrammseite kann direkt zwischen Stationen wechseln.",
    ),
    "tests": (
        "python3 tests/regression/check_ppfd_history_repair.py",
        "python3 tests/regression/check_environment_charts.py",
        "python3 tests/regression/check_spiderfarmer_ppfd_dashboard.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
