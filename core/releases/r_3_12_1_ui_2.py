"""Growstar release node 3.12.1 / UI.2."""

RELEASE = {
    "version": "3.12.1",
    "date": "2026-08-24",
    "phase": "UI.2",
    "title": "Ventilator-Oszillation im Dashboard korrekt anzeigen",
    "summary": (
        "Die Ventilatorstufe bleibt echter Spider-Farmer-getDevSta-Readback. "
        "Da GGS im Live-Status keinen aktuellen shakeLevel zurückliefert, zeigt "
        "Grow Control für die Oszillation nun den stationsbezogen gespeicherten "
        "Controller-Setpoint statt eines möglicherweise alten Config-Werts."
    ),
    "changes": (
        "fan.level bleibt unverändert echter getDevSta-Livewert.",
        "fan.oscillation_level wird im Dashboard aus DEVICE_PARAMS[device].controller.oscillation projiziert.",
        "Die Oszillationsquelle wird als configured_setpoint markiert.",
        "Ohne gespeicherten Oszillations-Setpoint wird kein alter Config-Wert als Live-Oszillation ausgegeben.",
        "Keine Änderung an Spider-Farmer-Schreibbefehlen, MQTT, Netzwerk, Shelly-Power-Gate oder Restart-Kopplung.",
    ),
    "tests": (
        "python3 tests/regression/check_dashboard_oscillation_setpoint.py",
        "python3 tests/regression/check_dashboard_controller_readback.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
