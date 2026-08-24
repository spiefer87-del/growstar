"""Growstar release node 3.12.2 / UI.3."""

RELEASE = {
    "version": "3.12.2",
    "date": "2026-08-24",
    "phase": "UI.3",
    "title": "Aktive Ventilator-Oszillation im Dashboard",
    "summary": (
        "Grow Control zeigt für die Ventilator-Oszillation jetzt den tatsächlich "
        "angewendeten Controller-Zustand bzw. den Setpoint des aktuell aktiven "
        "Growstar-Modus statt des alten globalen Controller-Defaults."
    ),
    "changes": (
        "Zuletzt erfolgreich angewendete Controller-Werte haben Vorrang.",
        "Fallback verwendet den getrennten Setpoint des aktiven Modus ON/TIME/ENV.",
        "Der alte globale params.controller-Wert wird nicht mehr als aktuelle Oszillation dargestellt.",
        "Ventilatorstufe bleibt echter Spider-Farmer-getDevSta-Livewert.",
        "Keine Änderung an MQTT, Spider-Farmer-Kommandos, Netzwerk, Shelly oder Restart-Kopplung.",
    ),
    "tests": (
        "python3 tests/regression/check_dashboard_oscillation_active_state.py",
        "python3 tests/regression/check_dashboard_oscillation_setpoint.py",
        "python3 tests/regression/check_dashboard_controller_readback.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
