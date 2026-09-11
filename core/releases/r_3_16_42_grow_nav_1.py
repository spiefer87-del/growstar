"""Growstar 3.16.42 / GROW.NAV.1 release metadata."""

RELEASE = {
    "version": "3.16.42",
    "date": "2026-09-11",
    "phase": "GROW.NAV.1",
    "title": "Grow-Control-Schnellmenü und Diagrammübersicht",
    "summary": (
        "Profile, Dashboard-Design und Umgebungsdiagramme werden direkt erreichbar; "
        "eine neue Übersicht trennt Auswertung von der Diagrammdaten-Verwaltung."
    ),
    "changes": [
        "Das Grow-Control-Klappmenü bietet direkte Einstiege in Profile und Dashboard-Design der Hauptstation.",
        "Die neue Diagrammübersicht zeigt jede Station mit Temperatur-, Feuchte-, VPD- und PPFD-Verlauf.",
        "Temperatur, Luftfeuchtigkeit und VPD lassen sich aus dem Schnellmenü direkt für die Hauptstation öffnen.",
        "Die bisherige Diagrammseite ist eindeutig als Import-, Export- und Reset-Verwaltung gekennzeichnet.",
        "Auch das Grow-Control-Dashboard verlinkt Profile, Design und die neue Diagrammübersicht.",
    ],
    "tests": [
        "python3 tests/regression/check_grow_control_quick_menu.py",
        "python3 tests/regression/check_app_shell_navigation.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
