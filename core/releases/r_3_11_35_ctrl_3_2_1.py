"""Growstar release node 3.11.35 / CTRL.3.2.1."""

RELEASE = {
    "version": "3.11.35",
    "date": "2026-08-23",
    "phase": "CTRL.3.2.1",
    "title": "CTRL.1 Regression an neues Power-Gate angepasst",
    "summary": (
        "CTRL.3.2.1 korrigiert ausschließlich die ältere "
        "check_controller_states.py-Regression. Seit CTRL.3.2 besitzt das "
        "Controller-Power-Gate einen read-only Shelly-Health-Fallback. Der "
        "isolierte Dummy-Test mockt diesen neuen Pfad nun explizit, statt auf "
        "reale Hardware-Assignments der Station 'default' zuzugreifen."
    ),
    "changes": (
        "Kein Produktivcode geändert.",
        "check_controller_states.py mockt device_assignment/get_endpoint_health im Dummy-Runtime-Test.",
        "OFF prüft zusätzlich, dass weder Assignment- noch Health-Fallback aufgerufen werden.",
        "Blockiertes Power-EIN verwendet bewusst configured=False und bestätigt weiterhin, dass kein Controllerwrite möglich ist.",
    ),
    "tests": (
        "python3 tests/regression/check_controller_states.py",
        "python3 tests/regression/check_controller_interval_ui.py",
        "python3 tests/regression/check_controller_mode_setpoints.py",
        "python3 tests/regression/check_controller_power_gate.py",
    ),
}
