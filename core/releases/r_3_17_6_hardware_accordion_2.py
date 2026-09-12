"""Growstar 3.17.6 / HARDWARE.ACCORDION.2 release metadata."""

RELEASE = {
    "version": "3.17.6",
    "date": "2026-09-12",
    "phase": "HARDWARE.ACCORDION.2",
    "title": "Geschlossene Module und Shelly-Untermenü",
    "summary": (
        "Hardware und Verbindungen starten übersichtlich geschlossen; "
        "erkannte Shellys liegen in einem eigenen Untermenü."
    ),
    "changes": [
        "Hardware und Verbindungen starten ohne geöffneten Hauptbereich.",
        "Explizite Direktlinks öffnen weiterhin gezielt den passenden Bereich.",
        "Gefundene Shelly-Gateways befinden sich in einem verschachtelten Klappbereich.",
        "Die Shelly-Trefferzahl bleibt sichtbar, Gerätedetails sind standardmäßig verborgen.",
    ],
    "tests": [
        "python3 tests/regression/check_connections_accordion.py",
        "python3 tests/regression/check_hardware_accordion.py",
        "python3 tests/regression/check_hardware_provisioning_discovery.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
