"""Growstar release node 3.13.0 / Shell.1."""

RELEASE = {
    "version": "3.13.0",
    "date": "2026-08-24",
    "phase": "SHELL.1",
    "title": "Globale Growstar Operations-Navigation",
    "summary": (
        "Growstar erhält eine zentrale, mobile Application-Shell mit Hamburger-"
        "Navigation und links einfahrendem Drawer. Die vorhandenen Fachseiten "
        "und sämtliche Regelungs-/Hardwarepfade bleiben unverändert."
    ),
    "changes": (
        "Feste, kompakte Operations-Leiste mit Hamburger-Menü auf angemeldeten Seiten.",
        "Von links einfahrender Navigations-Drawer mit Overlay und aktiver Bereichsmarkierung.",
        "Direktzugriffe auf Grow Control, Live-Steuerung, Sensoren, Hardware, Verbindungen, Spider Farmer, Energie, Diagramme und System.",
        "Pflanzenmanagement und Administration bleiben vollständig berechtigungsabhängig.",
        "Drawer schließt per Menüpunkt, Overlay, Schließen-Taste, Escape oder Linkswisch.",
        "Keyboard-Fokus wird im geöffneten Drawer gehalten und anschließend zurückgegeben.",
        "Versions- und Systemstatus sind kompakt im Drawer erreichbar.",
        "Bestehende Seiten, Controller-Stepper und Feedback-Helfer bleiben erhalten.",
        "Keine Änderung an Regelung, Runtime, MQTT, Spider Farmer, Shelly, Netzwerk, Safety oder Restart-Kopplung.",
    ),
    "tests": (
        "python3 tests/regression/check_app_shell_navigation.py",
        "python3 tests/regression/check_device_setpoint_steppers.py",
        "python3 tests/regression/check_dashboard_oscillation_active_state.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
