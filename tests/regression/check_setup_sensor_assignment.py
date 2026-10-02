#!/usr/bin/env python3
"""Station sensor assignment lives in Setup; sensor pages remain diagnostic."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
setup=(ROOT/'templates/grow_control_setup.html').read_text()
sources=(ROOT/'templates/grow_control_sensors.html').read_text()
detail=(ROOT/'templates/sensoren.html').read_text()


def check(condition,message):
    assert condition,message
    print('✅',message)


def main():
    check('class="assignment-select"' in setup and 'data-field="${field}"' in setup,
          'Setup bietet stationsbezogene Auswahlfelder')
    check('"temperature","humidity","ppfd","outside_temperature","outside_humidity","water_temperature"' in setup,
          'Innenwerte, PPFD, Außenwerte und Wassertemperatur haben eigene Ziele')
    check('sourceField' not in sources and 'drop-zone' not in sources and 'station-grid' not in sources,
          'Zentrale Sensorseite enthält weder Drag-and-Drop noch Stationen')
    check('setup-sensor-sources' not in setup and 'dragstart' not in setup and 'pointermove' not in setup,
          'Setup enthält keine zusätzliche Sensorliste oder Ziehgesten')
    check('id="temperature-source"' not in detail and 'id="outside-temperature-source"' not in detail
          and 'saveSensorAssignments' not in detail and 'id="TEMP_OFFSET"' in detail,
          'Stationssensorseite behält Messwerte und Offsets ohne Quellzuweisung')
    check('method:"POST"' in setup and 'body:JSON.stringify(payload)' in setup
          and 'field:sensorField(field)' in setup and 'refreshPreflights()' in setup,
          'Zuordnung verwendet bestehende API und aktualisiert LIVE-Preflight')
    check('(!id&&!["ppfd","outside_temperature","outside_humidity","water_temperature"].includes(field))' in setup
          and "'Nicht zugewiesen'" in setup,
          'Pflichtsensoren bleiben gesetzt, optionale Quellen lassen sich entfernen')
    check('select.addEventListener("change",()=>saveAssignment(select))' in setup
          and 'select.value=previous' in setup and 'select.dataset.current=id' in setup,
          'Auswahl speichert sofort und setzt bei Fehler auf den alten Wert zurück')
    check('selected&&!available' in setup and 'gespeichert' in setup,
          'Zwischenzeitlich offline Quellen bleiben als gespeicherte Option sichtbar')
    print('✅ SETUP.SENSORS.2 erfolgreich')


if __name__=='__main__':main()
