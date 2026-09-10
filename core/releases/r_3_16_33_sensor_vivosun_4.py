"""Growstar 3.16.33 / SENSOR.VIVOSUN.4 release metadata."""

RELEASE = {
    "version": "3.16.33",
    "date": "2026-09-10",
    "phase": "SENSOR.VIVOSUN.4",
    "title": "VS-THB1S schnell und transportneutral über Pico oder Raspberry",
    "summary": (
        "Growstar liest neue VIVOSUN AeroLab VS-THB1S jetzt auch am Pico W "
        "passiv aus ihren BLE-Advertisements. Raspberry und Pico führen "
        "denselben physischen Messkanal unter einer gemeinsamen Sensorquelle."
    ),
    "changes": (
        "Beide Pico-W-Firmwares dekodieren die offene 20-Byte-VIVOSUN-Werbung inklusive beider Messkanäle, Batteriespannung und Laufzeit.",
        "Neue namenlose VS-THB1S benötigen am Pico keine aktive GATT-Verbindung; ältere ThermoBeacon2-Geräte verwenden weiterhin den bisherigen GATT-Pfad.",
        "Das empfohlene Pico-Brückenintervall sinkt von 60 auf 10 Sekunden und darf bis auf fünf Sekunden reduziert werden.",
        "Direkt am Raspberry registrierte VIVOSUN-Sensoren erhalten einen eigenen Standardtakt von 10 Sekunden, ohne andere BLU-Geräte schneller abzufragen.",
        "Raspberry- und Pico-Messungen derselben BLE-Adresse und desselben Kanals werden unter einer transportneutralen Quellen-ID zusammengeführt.",
        "Bestehende Sensorzuweisungen mit alten hardware:- oder mqtt:-VIVOSUN-IDs werden beim Lesen weiterhin aufgelöst.",
        "Die Beispieladresse AA:BB:CC:DD:EE:FF wird auf dem Pico und auf der Sensorenseite ignoriert.",
        "Pico 1 und Pico 2 behalten identischen Brückencode; lokale WLAN- und MQTT-Zugangsdaten bleiben unverändert.",
    ),
    "tests": (
        "python3 tests/regression/check_vivosun_thb1s_integration.py",
        "python3 tests/regression/check_pico_vivosun_bridge.py",
        "python3 tests/regression/check_vivosun_source_handover.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
        "python3 -m compileall -q core services routes threads pico_sensor_01 pico_sensor_02",
    ),
}
