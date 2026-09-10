# Pico Sensorcontroller – lokale Konfiguration

Ab Growstar 3.8.0 liegen echte WLAN- und MQTT-Zugangsdaten nicht mehr im
GitHub-Repository. Für jeden Pico existiert eine Vorlage:

- `pico_sensor_01/config.example.py`
- `pico_sensor_02/config.example.py`

Für das Flashen wird daraus lokal eine `config.py` erstellt und mit den
tatsächlichen Zugangsdaten versehen. `config.py` wird von Git ignoriert. Die
bereits auf einem Pico gespeicherte Datei wird durch ein normales `git pull`
auf dem Raspberry Pi nicht verändert, weil der Pico ein eigenes Dateisystem
besitzt.

## VIVOSUN VS-THB1S als Pico-WLAN-Brücke

Beide Pico-W-Firmwareordner enthalten immer die Brückenfunktion. Sie wird auf
dem jeweiligen Pico aktiv, sobald mindestens ein Ziel in dessen lokaler
`config.py` eingetragen ist:

```python
VIVOSUN_BRIDGE_TARGETS = (
    {
        "address": "EE:65:C7:00:00:00",
        "name": "VIVOSUN Keller",
    },
)
```

Die Adresse kann über den vorhandenen VIVOSUN-Scan auf der Growstar-
Hardwareseite ermittelt werden. Dabei die Pair/Sensor-Taste am VS-THB1S etwa
drei Sekunden drücken und die VIVOSUN-App schließen.

Wichtig: Ein konkreter VIVOSUN-Sensor darf nur in der `config.py` **eines**
Picos stehen. Beide Picos dürfen als Brücke arbeiten, aber nicht gleichzeitig
dasselbe BLE-Gerät abfragen. Sinnvoll ist jeweils der räumlich nähere Pico.

Die Standardintervalle können bei Bedarf ebenfalls in `config.py` gesetzt
werden:

```python
VIVOSUN_BRIDGE_INTERVAL_SEC = 10
VIVOSUN_BLE_SCAN_TIMEOUT_SEC = 6
VIVOSUN_BLE_CONNECT_TIMEOUT_SEC = 12
VIVOSUN_BLE_READ_TIMEOUT_SEC = 4
```

Der Abfrageabstand wird von der Firmware auf mindestens fünf Sekunden begrenzt;
zehn Sekunden sind der empfohlene Wert. Neuere namenlose VS-THB1S werden dabei
ohne aktive Verbindung direkt aus dem offenen BLE-Advertisement gelesen. Für
ältere Geräte mit dem Namen `ThermoBeacon2` bleibt der GATT-Abruf erhalten.
Die lokalen DHT22-/DS18B20-Werte werden weiterhin alle fünf Sekunden gelesen.
Ein VIVOSUN-BLE-Fehler blockiert diese vorhandenen Messungen nicht.

Auf dem Pico müssen diese vier Dateien liegen:

- `main.py`
- `config.py`
- `umqttsimple.py`
- `vivosun_ble.py`

Benötigt wird eine aktuelle MicroPython-Firmware für den Raspberry Pi Pico W,
in der `import bluetooth` funktioniert. Nach dem ersten erfolgreichen Abruf
erscheinen in Growstar zwei normale MQTT-Quellen:

- `VIVOSUN … – Interner Sensor`
- `VIVOSUN … – Externer Fühler`

Beide Quellen können wie die vorhandenen Pico-Sensoren einer Station und einem
Messfeld zugeordnet werden. Der Pico sendet nur aktuelle Messwerte; State-
Pakete werden nicht retained gespeichert. Fällt der Pico aus, markiert dessen
MQTT-Last-Will auch die von ihm transportierten VIVOSUN-Quellen offline.

Raspberry und Pico verwenden für denselben BLE-Sensor dieselbe kanonische
Quellen-ID. Dadurch erscheint jeder interne beziehungsweise externe Kanal auf
der Sensorenseite nur einmal; der jeweils frischere Transport liefert die
angezeigten Werte. Die Beispieladresse `AA:BB:CC:DD:EE:FF` wird von Firmware
und Backend ignoriert und erzeugt keine leeren Sensorkarten mehr.
