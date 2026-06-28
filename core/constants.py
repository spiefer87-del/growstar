# core/constants.py

# Sensoren
SENSOR_WARN = 30
SENSOR_TIMEOUT = 120

# Datenbank
DB_INTERVAL = 30

# Shelly
ENERGY_INTERVAL = 30
FAILSAFE_INTERVAL = 30

# MQTT
MQTT_KEEPALIVE = 30

ENERGY_DEVICES = {
    "heating": ("IP_HEATING", "RELAY_HEATING"),
    "light": ("IP_LIGHT", "RELAY_LIGHT"),
    "fan": ("IP_FAN", "RELAY_FAN"),
    "vent": ("IP_VENT", "RELAY_VENT"),
    "irrigation": ("IP_IRRIGATION", "RELAY_IRRIGATION"),
    "humidifier": ("IP_HUMIDIFIER", "RELAY_HUMIDIFIER"),
    "dehumidifier": ("IP_DEHUMIDIFIER", "RELAY_DEHUMIDIFIER"),
    "light2": ("IP_LIGHT2", "RELAY_LIGHT2"),
    "vent2": ("IP_VENT2", "RELAY_VENT2"),
}
