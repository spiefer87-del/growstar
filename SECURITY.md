# Growstar Security

## Keine produktiven Secrets im Repository

In Git dürfen insbesondere **nicht** gespeichert werden:

- WLAN-Passwörter oder WPA-PSKs
- MQTT-Passwörter
- API-Tokens
- DuckDNS-/DNS-Provider-Tokens
- Flask-/Session-Secrets
- private Schlüssel oder Zertifikats-Private-Keys
- produktive Zugangsdaten für externe Dienste

Growstar speichert Laufzeit-Secrets außerhalb des Quellcodes. Für Pico-Geräte
werden echte Zugangsdaten ausschließlich in einer lokalen `config.py`
hinterlegt. Diese Datei ist ab Growstar 3.8.0 durch `.gitignore` geschützt;
im Repository liegen nur `config.example.py`-Vorlagen.

## Bereits veröffentlichte Secrets

Das Entfernen eines Secrets aus dem aktuellen Branch entfernt es **nicht**
automatisch aus älteren Git-Commits, Forks, Caches oder bereits erstellten
Clones. Sobald ein produktives Secret versehentlich versioniert wurde, gilt es
als kompromittiert und muss kontrolliert ersetzt/rotiert werden.

## Growstar-spezifische Secret-Speicher

- Flask-Session-Key: `instance/secret.key` oder `GROWSTAR_SECRET_KEY`
- WLAN des Growstar-Hosts: NetworkManager
- Pico-WLAN/MQTT: lokale, nicht versionierte `pico_sensor_*/config.py`
- lokale Runtime-Daten: `instance/`, `tent_configs/`, `backups/`

## Regel für neue Patches

Ein neuer Growstar-Patch darf keine produktiven Secrets, Debug-Backups oder
lokalen Laufzeitdaten in Git aufnehmen. Neue Regressionstests gehören unter
`tests/` und nicht mehr in den Repository-Root.
