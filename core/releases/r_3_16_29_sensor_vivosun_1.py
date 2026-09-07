"""Growstar 3.16.29 / SENSOR.VIVOSUN.1 release metadata."""

RELEASE = {
    "version": "3.16.29",
    "date": "2026-09-06",
    "phase": "SENSOR.VIVOSUN.1",
    "title": "VIVOSUN AeroLab VS-THB1S direkt per Raspberry-BLE",
    "summary": (
        "Growstar kann den VIVOSUN AeroLab Hygrometer Thermometer VS-THB1S "
        "ohne Hersteller-Cloud und ohne Shelly-Gateway suchen, verifizieren, "
        "auslesen und als zwei getrennte Sensorquellen verwenden."
    ),
    "changes": (
        "Die Hardware-Seite besitzt einen eigenen geführten VS-THB1S-Scan mit Pairing-Hinweis.",
        "Nur der Bluetooth-Lokalname ThermoBeacon2 wird als passendes Modell angeboten.",
        "Vor der Registrierung wird der Kandidat serverseitig erneut gescannt und durch einen echten Messwertabruf geprüft.",
        "Der Raspberry liest den proprietären GATT-Status per Kommando 0x0D direkt über Bleak und BlueZ.",
        "Interner Sensor und externer Fühler werden getrennt dekodiert und als eigene Temperatur-/Feuchtequellen veröffentlicht.",
        "Die Gerätedetailseite zeigt beide Kanäle, lokalen Transport, letzten BLE-Fehler und einen manuellen Sofort-Read.",
        "Der vorhandene BLU-Hintergrundthread aktualisiert registrierte VS-THB1S-Sensoren im normalen Sensorintervall.",
        "Hardware-Inventar und Neustart-Recovery stellen den Sensor auch ohne Shelly-Gateway wieder her.",
        "Fehlerhafte oder unplausible BLE-Pakete werden verworfen; alte Werte werden nicht als neue Messung ausgegeben.",
        "Scan und dauerhafte Registrierung bleiben über hardware.control beziehungsweise hardware.configure getrennt geschützt.",
    ),
    "tests": (
        "python3 tests/regression/check_vivosun_thb1s_integration.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
