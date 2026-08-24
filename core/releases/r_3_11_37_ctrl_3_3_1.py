"""Growstar release node 3.11.37 / CTRL.3.3.1."""

RELEASE = {
    "version": "3.11.37",
    "date": "2026-08-24",
    "phase": "CTRL.3.3.1",
    "title": "Veralteten device_assignment-Mock aus Power-Gate-Test entfernt",
    "summary": (
        "CTRL.3.3.1 ändert ausschließlich die Regression "
        "check_controller_power_gate.py. CTRL.3.3 entfernte device_assignment "
        "aus core.controller_states, ein einzelner alter Mock blieb im Test "
        "jedoch bestehen und verursachte einen AttributeError."
    ),
    "changes": (
        "Kein Produktivcode geändert.",
        "Der letzte Mock auf core.controller_states.device_assignment wurde entfernt.",
        "Runtime-EIN prüft nun korrekt, dass get_endpoint_health nicht benötigt wird.",
        "Die übrigen Runtime-Config-, Health- und Power-AUS-Regressionen bleiben erhalten.",
    ),
}
