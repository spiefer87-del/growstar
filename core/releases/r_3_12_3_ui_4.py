"""Growstar release node 3.12.3 / UI.4."""

RELEASE = {
    "version": "3.12.3",
    "date": "2026-08-24",
    "phase": "UI.4",
    "title": "Regressionstests an aktive Oszillationslogik angleichen",
    "summary": (
        "Die UI.3-Produktionslogik ist korrekt, aber zwei ältere UI.1/UI.2-"
        "Regressionstests prüften absichtlich die inzwischen ersetzte Architektur. "
        "UI.4 aktualisiert ausschließlich diese Guards auf die neue aktive "
        "Controller-State-Logik."
    ),
    "changes": (
        "check_dashboard_oscillation_setpoint.py akzeptiert applied_controller_state und active_mode_setpoint.",
        "check_dashboard_controller_readback.py erlaubt den Sendecache ausschließlich im fan-Oszillations-Sonderfall.",
        "Keine Produktionslogik verändert.",
        "Keine Änderung an MQTT, Spider-Farmer-Kommandos, Netzwerk, Shelly oder Restart-Kopplung.",
    ),
    "tests": (
        "python3 tests/regression/check_dashboard_oscillation_active_state.py",
        "python3 tests/regression/check_dashboard_oscillation_setpoint.py",
        "python3 tests/regression/check_dashboard_controller_readback.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
