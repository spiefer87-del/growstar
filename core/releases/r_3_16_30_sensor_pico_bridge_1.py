"""Growstar 3.16.30 / SENSOR.PICO.BRIDGE.1 release metadata."""

RELEASE = {
    "version": "3.16.30",
    "date": "2026-09-07",
    "phase": "SENSOR.PICO.BRIDGE.1",
    "title": "Beide Pico W als VIVOSUN-BLE-zu-WLAN-Brücke",
    "summary": (
        "Die beiden vorhandenen Pico-Sensorcontroller können zusätzlich ihre "
        "räumlich zugeordneten VIVOSUN AeroLab VS-THB1S per BLE auslesen und "
        "die Messwerte über das vorhandene WLAN/MQTT-Netz an Growstar senden."
    ),
    "changes": (
        "Beide Pico-Firmwareordner enthalten denselben eigenständigen VS-THB1S-GATT-Client.",
        "Der Pico scannt eine fest zugewiesene MAC-Adresse, prüft ThermoBeacon2, aktiviert Notifications und fordert Statuskommando 0x0D an.",
        "Interner Sensor und externer Fühler werden als getrennte virtuelle MQTT-Sensorquellen veröffentlicht.",
        "Die vorhandenen DHT22-/DS18B20-Messungen laufen unverändert und werden vor jeder fälligen BLE-Abfrage gesendet.",
        "BLE-Fehler werden isoliert behandelt und markieren die betroffenen Brückenquellen offline, ohne den normalen Pico-Sensorzyklus zu stoppen.",
        "Vorhandene lokale config.py-Dateien bleiben kompatibel; erst VIVOSUN_BRIDGE_TARGETS aktiviert konkrete Ziele.",
        "Ein Mindestintervall von 30 Sekunden begrenzt BLE- und Batterielast.",
        "Growstar übernimmt Brücken-ID, BLE-Adresse, Protokoll und Kanal in das MQTT-Hardwareinventar.",
        "Das MQTT-Last-Will eines ausgefallenen Pico markiert auch dessen virtuelle VIVOSUN-Quellen offline.",
        "Die Hardwareübersicht zeigt bei virtuellen Sensoren den verantwortlichen Pico und die BLE-Adresse.",
        "Die Pico-Konfigurationsdokumentation beschreibt Zuordnung, Firmwarevoraussetzung und benötigte Dateien.",
    ),
    "tests": (
        "python3 tests/regression/check_pico_vivosun_bridge.py",
        "python3 tests/regression/check_vivosun_thb1s_integration.py",
        "python3 tests/regression/check_sensor_ppfd_assignment_hardware.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
