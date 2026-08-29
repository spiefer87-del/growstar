"""Growstar release node 3.12.4 / UI.5."""

RELEASE = {
    "version": "3.12.4",
    "date": "2026-08-24",
    "phase": "UI.5",
    "title": "Dezente Plus/Minus-Steuerung an Controller-Slidern",
    "summary": (
        "Controller-Slider in der Geräteansicht erhalten kompakte Minus- und "
        "Plus-Tasten. Jeder Tipp verändert exakt um den im Controller-Schema "
        "definierten Schritt und nutzt weiterhin den bestehenden Speichern-Workflow."
    ),
    "changes": (
        "Minus-Taste links und Plus-Taste rechts neben jedem Controller-Slider.",
        "Schrittweite wird automatisch aus dem vorhandenen spec.step übernommen.",
        "Min-/Max-Grenzen werden automatisch eingehalten.",
        "Slider, Zahlenfeld und Level-Anzeige bleiben synchron.",
        "Funktioniert generisch für Ventilatorstufe, Oszillation, Abluft/Gebläse und Licht-Dimmung.",
        "Funktioniert in Dauerbetrieb, Zeitsteuerung, ENV und beiden Intervallphasen.",
        "Tastendruck ändert nur das Formular; Hardware-Übernahme bleibt beim grünen Speichern-Button.",
        "Keine Änderung an Controller-Backend, Spider Farmer, Shelly, MQTT, Netzwerk oder Restart-Kopplung.",
    ),
    "tests": (
        "python3 tests/regression/check_device_setpoint_steppers.py",
        "python3 tests/regression/check_dashboard_oscillation_active_state.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
