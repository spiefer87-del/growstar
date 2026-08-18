# ==========================================
# Growstar Pico Sensorcontroller – Beispielkonfiguration
# ==========================================
#
# Diese Datei nach "config.py" kopieren und NUR auf dem lokalen
# Entwicklungsrechner bzw. direkt auf dem Pico mit echten Zugangsdaten füllen.
# config.py wird von Growstar 3.8.0 per .gitignore ausgeschlossen.
#
# Niemals echte WLAN-/MQTT-Zugangsdaten in config.example.py eintragen.

# WLAN
SSID = "DEIN_WLAN_NAME"
PASSWORD = "DEIN_WLAN_PASSWORT"

# MQTT Broker (Growstar Raspberry Pi)
MQTT_BROKER = "192.168.1.100"
MQTT_PORT = 1883
MQTT_USER = None
MQTT_PASSWORD = None

# Physische Geräteidentität, unabhängig vom Einsatzort.
DEVICE_ID = "pico_01"
DEVICE_NAME = "Pico Sensor 1"
DEVICE_MODEL = "Raspberry Pi Pico W"
FIRMWARE_VERSION = "growstar-pico-mqtt-2"

CLIENT_ID = ("growstar_" + DEVICE_ID).encode()
TOPIC_STATE = ("growstar/sensors/%s/state" % DEVICE_ID).encode()
TOPIC_STATUS = ("growstar/sensors/%s/status" % DEVICE_ID).encode()

# Sensor-Pins
DHT22_PIN = 15
DS18B20_PIN = 16
SAFE_MODE_PIN = 0

# Intervalle
PUBLISH_INTERVAL_SEC = 5
WIFI_CONNECT_TIMEOUT_SEC = 20
WIFI_RETRY_SEC = 5
MQTT_RETRY_SEC = 5
DS_RESCAN_INTERVAL_SEC = 30
