"""Growstar 3.17.1 / ENERGY.RESET.1 release metadata."""

RELEASE = {
    "version": "3.17.1",
    "date": "2026-09-11",
    "phase": "ENERGY.RESET.1",
    "title": "Energie-Abrechnungstag folgt Reset-Uhrzeit",
    "summary": (
        "Tagesverbrauch, Verlauf und Tagespeaks wechseln nun gemeinsam erst zur "
        "konfigurierten Reset-Uhrzeit statt unabhängig davon um Mitternacht."
    ),
    "changes": [
        "05:30 bleibt auch zwischen 00:00 und 05:29 die wirksame Tagesgrenze.",
        "Scheduler, Tagesoffsets, Historie und Peaks verwenden dieselbe Zeitlogik.",
        "Automatische und manuelle Tagesresets speichern Zeitpunkt, Auslöser und Umfang.",
        "Energie-Einstellungen zeigen letzten Reset, aktuellen Abrechnungstag und nächsten Reset.",
        "Die Energieübersicht zeigt die aktive Reset-Uhrzeit und den Beginn des Tageswerts.",
    ],
    "tests": [
        "python3 tests/regression/check_energy_day_reset_schedule.py",
        "python3 tests/regression/check_energy_navigation_category.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
