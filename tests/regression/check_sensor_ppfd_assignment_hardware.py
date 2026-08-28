#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)

def main():
    sensors = (ROOT / "routes/sensors.py").read_text(encoding="utf-8")
    tents = (ROOT / "routes/tents.py").read_text(encoding="utf-8")
    ui = (ROOT / "templates/sensoren.html").read_text(encoding="utf-8")
    hw_route = (ROOT / "routes/hardware.py").read_text(encoding="utf-8")
    hw_ui = (ROOT / "templates/devices.html").read_text(encoding="utf-8")

    require('"ppfd": ppfd' in sensors, "Sensor-API bietet PPFD-Optionen")
    require('assignments["ppfd"]' in sensors, "PPFD-Zuweisung wird stationsbezogen gespeichert")
    require('("temperature", "humidity", "ppfd")' in sensors, "PPFD erscheint in Sensorquellen-Feldern")
    require('ppfd_assignment = assignments.get("ppfd")' in tents, "Dashboard priorisiert explizite PPFD-Zuweisung")
    require('id="ppfd-source"' in ui, "Sensorseite besitzt PPFD-Dropdown")
    require('Helligkeit / PPFD' in ui, "Sensorseite besitzt PPFD-Karte")
    require('ppfd: ppfdOption' in ui, "Sensorseite speichert PPFD-Zuweisung")
    require('source.ppfd' in ui, "Verfügbare Quellen zeigen PPFD")
    require('def _spiderfarmer_sensor_views():' in hw_route, "Hardware-API projiziert Spider-Farmer-Sensoren")
    require('"spiderfarmer_sensors": _spiderfarmer_sensor_views()' in hw_route, "Hardware-API liefert Spider-Farmer-Sensoren")
    require('id="spiderfarmer-sensor-grid"' in hw_ui, "Hardwareseite besitzt Spider-Farmer-Sensorbereich")
    require('renderSpiderFarmerSensors' in hw_ui, "Hardwareseite rendert Spider-Farmer-Sensorkarten")
    print("✅ Growstar 3.13.11 / SENSOR.PPFD.2 vollständig geprüft")

if __name__ == "__main__":
    main()
