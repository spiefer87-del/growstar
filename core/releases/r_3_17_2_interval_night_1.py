"""Growstar 3.17.2 / INTERVAL.NIGHT.1 release metadata."""

RELEASE = {
    "version": "3.17.2",
    "date": "2026-09-12",
    "phase": "INTERVAL.NIGHT.1",
    "title": "Tag-/Nachtwerte im Intervall und vollständiger Reset-Nachweis",
    "summary": (
        "Intervallgeräte können nachts automatisch eigene Controllerwerte für "
        "Phase A und B verwenden; Energie-Gesamtresets erhalten einen sichtbaren Zeitstempel."
    ),
    "changes": [
        "Optionale Nachtwerte für Controller-Level und Oszillation in Phase A und B.",
        "Automatische Umschaltung anhand der vorhandenen Tag-/Nacht-Zeiten der Station.",
        "Dauer und Shelly-Power der Phasen bleiben als sichere gemeinsame Basis unverändert.",
        "Alte Intervallkonfigurationen bleiben kompatibel und verwenden nachts ihre Tagwerte.",
        "Energie-Einstellungen und Übersicht zeigen Datum und Uhrzeit des letzten Gesamt-Resets.",
    ],
    "tests": [
        "python3 tests/regression/check_interval_day_night.py",
        "python3 tests/regression/check_controller_states.py",
        "python3 tests/regression/check_controller_interval_ui.py",
        "python3 tests/regression/check_energy_day_reset_schedule.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
