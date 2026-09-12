"""Growstar 3.17.4 / CONNECTIONS.ACCORDION.1 release metadata."""

RELEASE = {
    "version": "3.17.4",
    "date": "2026-09-12",
    "phase": "CONNECTIONS.ACCORDION.1",
    "title": "Übersichtliche Verbindungsverwaltung als Akkordeon",
    "summary": (
        "Kamera-, Strom- und Controller-Verbindungen sind in drei exklusive, "
        "mobilfreundliche Klappbereiche gegliedert."
    ),
    "changes": [
        "Kameras, Shelly-Stromversorgung und Controller erhalten eigene Klappbereiche.",
        "Beim Öffnen eines Bereichs schließt Growstar den zuvor geöffneten automatisch.",
        "Ein geöffneter Bereich kann vollständig zugeklappt werden.",
        "Direktlinks zur Kameraverbindung öffnen weiterhin automatisch den Kamerabereich.",
        "Speicheraktionen bleiben am unteren Rand des geöffneten Bereichs leichter erreichbar.",
    ],
    "tests": [
        "python3 tests/regression/check_connections_accordion.py",
        "python3 tests/regression/check_hardware_module_navigation.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
