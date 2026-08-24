"""Growstar release node 3.11.38 / CORE.RELEASE.GUARD."""

RELEASE = {
    "version": "3.11.38",
    "date": "2026-08-24",
    "phase": "CORE.RELEASE.GUARD",
    "title": "Release-Loader gegen ungültige Release-Nodes absichern",
    "summary": (
        "3.11.38 repariert die fehlenden tests-Pflichtfelder in den Release-Nodes "
        "3.11.36 und 3.11.37 und ergänzt einen Regressionstest, der künftig alle "
        "Release-Dateien durch den echten Growstar-Release-Loader validiert."
    ),
    "changes": (
        "r_3_11_36_ctrl_3_3.py erhält das vorgeschriebene tests-Feld.",
        "r_3_11_37_ctrl_3_3_1.py erhält das vorgeschriebene tests-Feld.",
        "check_release_loader.py importiert den echten Release-Loader und validiert alle Release-Nodes.",
        "Ein fehlendes Pflichtfeld wird damit künftig vor einem Service-Neustart erkannt.",
        "Kein Controller-, Shelly- oder Spider-Farmer-Produktivcode geändert.",
    ),
    "tests": (
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_controller_states.py",
        "python3 tests/regression/check_controller_interval_ui.py",
        "python3 tests/regression/check_controller_mode_setpoints.py",
        "python3 tests/regression/check_controller_power_gate.py",
    ),
}
