# ==========================================
# Growstar Pico Sensorcontroller 2
# ==========================================
# WICHTIG: Der Pico ist NICHT an ein Zelt gebunden.
# Die Zuordnung zu Zelt 1/2/3 erfolgt ausschließlich in Growstar per Drag&Drop.

# WLAN
SSID = "FRITZ!Box 6660 Cable DD"
PASSWORD = "47720959337135414729"

# MQTT Broker (Growstar Raspberry Pi)
MQTT_BROKER = "192.168.178.66"
MQTT_PORT = 1883
MQTT_USER = None
MQTT_PASSWORD = None

# Physische Geräteidentität, unabhängig vom Einsatzort.
# Für weitere Controller z. B. pico_03 / "Pico Sensor 3".
DEVICE_ID = "pico_02"
DEVICE_NAME = "Pico Sensor 2"
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
