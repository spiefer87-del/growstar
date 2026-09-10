"""Growstar 3.16.32 / SENSOR.VIVOSUN.3 release metadata."""

RELEASE = {
    "version": "3.16.32",
    "date": "2026-09-10",
    "phase": "SENSOR.VIVOSUN.3",
    "title": "VS-THB1S-Messwerte passiv aus BLE-Advertisements lesen",
    "summary": (
        "Growstar liest neuere namenlose VIVOSUN AeroLab VS-THB1S direkt aus "
        "ihren offenen 20-Byte-Advertisements aus. Dadurch funktionieren "
        "Registrierung und Hintergrundaktualisierung auch dann, wenn der Sensor "
        "eine aktive GATT-Verbindung des Raspberry ablehnt."
    ),
    "changes": (
        "Der Raspberry dekodiert interne und externe Temperatur sowie Luftfeuchtigkeit direkt aus dem BLE-Advert.",
        "Batteriespannung und Sensorlaufzeit werden aus demselben passiven Datenpaket übernommen.",
        "Namenlose Geräte mit passender FFF0- und ManufacturerData-Signatur benötigen keine aktive GATT-Verbindung mehr.",
        "Der bestehende GATT-Pfad mit Statuskommando 0x0D bleibt für ältere ThermoBeacon2-Geräte erhalten.",
        "Advertisement-Payloads werden vor der Gerätefreigabe vollständig auf Länge und plausible Messwerte geprüft.",
        "Growstar speichert Messwertquelle, Batteriespannung, Sensorlaufzeit und ManufacturerData-ID im Hardwareinventar.",
        "Leere Timeout-Ausnahmen zeigen künftig mindestens ihren Fehlerklassennamen an.",
        "Die Hardwareseite beschreibt den passiven, verbindungslosen Raspberry-Auslesepfad korrekt.",
        "Pico-W-Konfiguration, WLAN-Zugangsdaten, Cloudfunktionen und Relaissteuerung bleiben unverändert.",
    ),
    "tests": (
        "python3 tests/regression/check_vivosun_thb1s_integration.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 -m compileall -q core/hardware/vivosun.py services/hardware.py core/releases/r_3_16_32_sensor_vivosun_3.py",
    ),
}
