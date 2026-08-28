"""Growstar 3.13.11 / SENSOR.PPFD.2 release metadata."""

RELEASE = {
    "version": "3.13.11",
    "date": "2026-08-27",
    "phase": "SENSOR.PPFD.2",
    "title": "PPFD-Zuweisung und Spider-Farmer-Sensoren in Hardware",
    "summary": (
        "PPFD wird als eigenständig zuweisbare stationsbezogene Sensorquelle "
        "geführt. Spider-Farmer-Umgebungssensoren erscheinen zusätzlich in "
        "Growstars zentraler Hardwareübersicht."
    ),
    "changes": (
        "Sensorzuweisungen unterstützen temperature, humidity und ppfd getrennt.",
        "Zelt-Sensorseite erhält eine eigene Helligkeit/PPFD-Auswahl.",
        "Dashboard verwendet vorrangig die explizit gespeicherte PPFD-Quelle.",
        "Bestehende 3.13.10-Zuordnung bleibt als Migrations-Fallback erhalten.",
        "Hardwareübersicht zeigt Spider-Farmer-GGS-Sensoren mit Temperatur, Feuchte und PPFD.",
        "Keine Änderung an Regelung, Aktorik, D734, C5B8-Controller oder Power-Strip-Outlets.",
    ),
    "tests": (
        "python3 tests/regression/check_sensor_ppfd_assignment_hardware.py",
        "python3 tests/regression/check_spiderfarmer_ppfd_dashboard.py",
        "python3 tests/regression/check_spiderfarmer_ps_controller_transport.py",
        "python3 tests/regression/check_spiderfarmer_writer_reconnect_guard.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
