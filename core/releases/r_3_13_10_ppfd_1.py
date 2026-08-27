"""Growstar 3.13.10 / PPFD.1 release metadata."""

RELEASE = {
    "version": "3.13.10",
    "date": "2026-08-27",
    "phase": "PPFD.1",
    "title": "Spider-Farmer PPFD im Grow-Control-Dashboard",
    "summary": (
        "Der bereits im C5B8/GGS-Sensor-Readmodel vorhandene PPFD-Wert wird "
        "als normale Growstar-Sensorgröße veröffentlicht und stationsbezogen "
        "in der vorbereiteten Helligkeits-Kachel angezeigt."
    ),
    "changes": (
        "core.sensor_sources unterstützt ppfd als normalisierten Messwert.",
        "services.spiderfarmer publiziert sensor.ppfd in die Growstar-Sensorquelle.",
        "Die Tent-State-API übernimmt PPFD aus der bereits zugeordneten Spider-Farmer-Umgebungsquelle.",
        "Die vorhandene Dashboard-Kachel light_level bleibt als Design-Key erhalten.",
        "Die Anzeige verwendet µmol/m²/s statt einer fachlich falschen Lux-Umrechnung.",
        "Keine Änderung an Regelung, Aktorik, D734, C5B8-Controllerbefehlen oder Steckdosen.",
    ),
    "tests": (
        "python3 tests/regression/check_spiderfarmer_ppfd_dashboard.py",
        "python3 tests/regression/check_spiderfarmer_ps_controller_transport.py",
        "python3 tests/regression/check_spiderfarmer_writer_reconnect_guard.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
