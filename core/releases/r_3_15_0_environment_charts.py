"""Growstar 3.15.0 / ENV.CHARTS.1 release metadata."""

RELEASE = {
    "version": "3.15.0",
    "date": "2026-08-29",
    "phase": "ENV.CHARTS.1",
    "title": "Moderne Umgebungsdiagramme mit PPFD-Historie",
    "summary": "Temperatur, Luftfeuchtigkeit, VPD und PPFD nutzen eine gemeinsame moderne Verlaufsansicht.",
    "changes": (
        "PPFD wird stationsbezogen in SQLite gespeichert.",
        "temp_history erhält migrationssicher die Spalte ppfd.",
        "PPFD-Aufzeichnung läuft unabhängig von Temp/Hum.",
        "History-API unterstützt type=ppfd.",
        "Direktumschaltung Temperatur, Feuchte, VPD und Helligkeit.",
        "Zeiträume 1h, 6h, 24h und 7 Tage.",
        "Aktuell, Minimum, Durchschnitt und Maximum.",
        "Sollwertlinie für Temperatur und Feuchtigkeit.",
        "Helligkeits-Kachel führt direkt zum PPFD-Diagramm.",
        "Regelung und Hardwaresteuerung bleiben unverändert.",
    ),
    "tests": (
        "python3 tests/regression/check_environment_charts.py",
        "python3 tests/regression/check_spiderfarmer_ppfd_dashboard.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
