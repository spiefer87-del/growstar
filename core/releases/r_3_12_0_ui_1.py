"""Growstar release node 3.12.0 / UI.1."""

RELEASE = {
    "version": "3.12.0",
    "date": "2026-08-24",
    "phase": "UI.1",
    "title": "Controller-Livewerte im Grow-Control-Dashboard",
    "summary": (
        "Growstar 3.12 startet die UI-Weiterentwicklung. Die Gerätekacheln im "
        "stationsbezogenen Grow-Control-Dashboard zeigen jetzt die bereits "
        "vorhandenen, tatsächlich zurückgelesenen Spider-Farmer-Controllerwerte."
    ),
    "changes": (
        "Beleuchtung und Licht 2 zeigen den zurückgelesenen Dimm-Level.",
        "Ventilator und Ventilator 2 zeigen Stufe und Oszillationslevel.",
        "Lüfter/Abluft zeigt den zurückgelesenen Blower-Level als Leistung.",
        "Die Zusatzanzeige erscheint nur bei physisch bestätigt eingeschaltetem Gerät.",
        "Safety-, Shadow-, Zuordnungs- und Hardwarefehler behalten Vorrang.",
        "Der State-Payload erhält dafür ein read-only controller_readback-Feld.",
        "Keine Änderung am Controller-Schreibpfad, MQTT, Shelly-Power-Gate oder an Sollwerten.",
    ),
    "tests": (
        "python3 tests/regression/check_dashboard_controller_readback.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
