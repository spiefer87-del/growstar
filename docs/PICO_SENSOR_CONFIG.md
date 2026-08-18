# Pico Sensorcontroller – lokale Konfiguration

Ab Growstar 3.8.0 liegen echte WLAN- und MQTT-Zugangsdaten nicht mehr im
GitHub-Repository.

Für jeden Pico existiert eine Vorlage:

- `pico_sensor_01/config.example.py`
- `pico_sensor_02/config.example.py`

Für das Flashen wird daraus lokal eine `config.py` erstellt und mit den
tatsächlichen Zugangsdaten versehen. `config.py` wird von Git ignoriert.

Die bereits auf einem Pico gespeicherte Datei wird durch ein normales
`git pull` auf dem Raspberry Pi nicht verändert, weil der Pico ein eigenes
Dateisystem besitzt.

Langfristig kann Growstar die Pico-Erstinbetriebnahme noch um eine
browserbasierte Provisionierung erweitern; 3.8.0 trennt zunächst sauber
Firmware und produktive Secrets.
