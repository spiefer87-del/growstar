"""Growstar release node 3.11.33 / CTRL.3.1."""

RELEASE = {
    "version": "3.11.33",
    "date": "2026-08-23",
    "phase": "CTRL.3.1",
    "title": "Intervall-Regression an CTRL.3-Oberfläche angepasst",
    "summary": (
        "CTRL.3.1 korrigiert ausschließlich eine veraltete statische "
        "Regression aus CTRL.2. Die Produktivlogik bleibt unverändert. "
        "Die Prüfung akzeptiert nun die in CTRL.3 aktualisierte Formulierung "
        "der Shelly-Priorität, ohne die Sicherheitsanforderung abzuschwächen."
    ),
    "changes": (
        "check_controller_interval_ui.py prüft die aktuelle CTRL.3-Formulierung der Shelly-Priorität.",
        "Keine Änderung an core/control.py, core/controller_states.py oder der Geräteoberfläche.",
        "Die Regression verlangt weiterhin ausdrücklich, dass Power / Ein-Aus beim Shelly bleibt.",
        "Die Intervallprüfung für Phase B mit Shelly-Power EIN bleibt unverändert bestehen.",
    ),
    "tests": (
        "python3 tests/regression/check_controller_states.py",
        "python3 tests/regression/check_controller_interval_ui.py",
        "python3 tests/regression/check_controller_mode_setpoints.py",
    ),
}
