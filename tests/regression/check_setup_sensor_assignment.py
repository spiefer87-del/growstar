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
    check('id="setup-sensor-sources"' in setup and 'data-field="${field}"' in setup,
          'Setup bietet Quelle und stationsbezogene Drop-Ziele')
    check('"temperature","humidity","ppfd","outside_temperature","outside_humidity"' in setup,
          'Innenwerte, PPFD und Außenwerte haben eigene Ziele')
    check('sourceField' not in sources and 'drop-zone' not in sources and 'station-grid' not in sources,
          'Zentrale Sensorseite enthält weder Drag-and-Drop noch Stationen')
    check('id="temperature-source"' not in detail and 'id="outside-temperature-source"' not in detail
          and 'saveSensorAssignments' not in detail and 'id="TEMP_OFFSET"' in detail,
          'Stationssensorseite behält Messwerte und Offsets ohne Quellzuweisung')
    check('method:"POST"' in setup and 'body:JSON.stringify(payload)' in setup
          and 'field:sensorField(field)' in setup and 'refreshPreflights()' in setup,
          'Zuordnung verwendet bestehende API und aktualisiert LIVE-Preflight')
    check('if(!id&&!["ppfd","outside_temperature","outside_humidity"].includes(field))return' in setup,
          'Pflichtsensoren lassen sich nicht versehentlich löschen')
    check('pointermove' in setup and 'pointerup' in setup and 'dragstart' in setup
          and 'z.addEventListener("click"' in setup,
          'Desktop-Drag, mobile Pointer-Geste und Auswahl per Antippen sind vorhanden')
    print('✅ SETUP.SENSORS.1 erfolgreich')


if __name__=='__main__':main()
