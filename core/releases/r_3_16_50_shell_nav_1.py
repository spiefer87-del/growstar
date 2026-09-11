"""Growstar 3.16.50 / SHELL.NAV.1 release metadata."""

RELEASE = {
    "version": "3.16.50",
    "date": "2026-09-11",
    "phase": "SHELL.NAV.1",
    "title": "Durchgängige Hamburger-Navigation",
    "summary": (
        "Alle aktiven Hardware-, Sensor-, Profil- und Diagrammseiten verwenden die "
        "zentrale Growstar-App-Shell; das veraltete System-Doppeldashboard ist stillgelegt."
    ),
    "changes": [
        "Geräteübersicht, Gateway- und Bluetooth-Details besitzen nun das Hamburger-Menü.",
        "Spider Farmer, Profile, Klima, Sensorzuordnung und Diagrammseiten nutzen dieselbe Navigation.",
        "Der redundante Systemstatus-Eintrag wurde aus Hardware-Startseite und Hauptmenü entfernt.",
        "Die alte URL /system leitet kompatibel auf Hardware & Setup weiter.",
        "Aktuelle Raspberry-Systemdaten bleiben unverändert über Watchdog erreichbar.",
    ],
    "tests": [
        "python3 tests/regression/check_app_shell_page_coverage.py",
        "python3 tests/regression/check_app_shell_navigation.py",
        "python3 tests/regression/check_hardware_module_navigation.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
