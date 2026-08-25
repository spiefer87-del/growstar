"""Growstar release node 3.13.2 / Shell.3."""
RELEASE = {
    "version": "3.13.2",
    "date": "2026-08-25",
    "phase": "SHELL.3",
    "title": "Modulare Navigation für Grow Control, Pflanzen und Administrator",
    "summary": (
        "Die Operations-Navigation wird in drei klare Fachmodule gegliedert. "
        "Grow Control und Pflanzenmanagement sind klappbar; technische Grow-Control-"
        "Werkzeuge liegen direkt im Grow-Control-Untermenü. Administratorfunktionen "
        "stehen als eigener, berechtigungsabhängiger Bereich bereit."
    ),
    "changes": (
        "Grow Control erhält ein eigenes klappbares Untermenü.",
        "Hardware, Verbindungen, Spider Farmer, Energie, Diagramme, Watchdog, Setup und Systemstatus liegen unter Grow Control / Technik.",
        "Pflanzenmanagement bleibt als separates klappbares Fachmodul erhalten.",
        "Administrator wird als eigener Bereich mit Übersicht, Benutzern, Rollen und Audit dargestellt.",
        "Administrator-Unterpunkte bleiben streng an die vorhandenen Berechtigungen gebunden.",
        "Aktive Fachmodule öffnen automatisch und markieren den aktuellen Unterpunkt.",
        "Keine Änderung an Regelung, Runtime, MQTT, Spider Farmer, Shelly, Netzwerk, Safety oder Restart-Kopplung.",
    ),
    "tests": (
        "python3 tests/regression/check_app_shell_navigation.py",
        "python3 tests/regression/check_device_setpoint_steppers.py",
        "python3 tests/regression/check_dashboard_oscillation_active_state.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
