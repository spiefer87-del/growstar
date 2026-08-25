"""Growstar release node 3.13.1 / Shell.2."""

RELEASE = {
    "version": "3.13.1",
    "date": "2026-08-25",
    "phase": "SHELL.2",
    "title": "Stabile Drawer-Skalierung und Pflanzen-Klappnavigation",
    "summary": (
        "Die globale Growstar-Navigation bleibt jetzt auf allen Fachseiten pixelstabil, "
        "auch wenn eine Seite ihre eigene html-Schriftbasis ändert. Pflanzenmanagement "
        "erhält zusätzlich eine eigene klappbare Navigation."
    ),
    "changes": (
        "Shell-Typografie ist von seitenlokalen rem/root-font-size-Regeln entkoppelt.",
        "Live-Steuerung mit mobilem html font-size 11px verändert den Drawer nicht mehr.",
        "Pflanzenmanagement besitzt einen eigenen Navigationsabschnitt.",
        "Pflanzen-Untermenü ist separat ein- und ausklappbar.",
        "Direktlinks auf Übersicht, Pflanzen, Timeline, Sorten, Genetik & Mütter, Vermehrung, Durchgänge und Betriebsjournal.",
        "Aktive Pflanzen-Unterseite öffnet das Klappmenü automatisch und wird markiert.",
        "Keine Änderung an Regelung, Runtime, MQTT, Spider Farmer, Shelly, Netzwerk, Safety oder Restart-Kopplung.",
    ),
    "tests": (
        "python3 tests/regression/check_app_shell_navigation.py",
        "python3 tests/regression/check_device_setpoint_steppers.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
