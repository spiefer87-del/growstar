import network
import time
import machine
from umqttsimple import MQTTClient

# ===== WLAN =====
SSID = 'FRITZ!Box 6660 Cable DD'
PASSWORD = '47720959337135414729'

# ===== MQTT =====
MQTT_BROKER = "192.168.178.65"  # IP vom Raspberry Pi
CLIENT_ID = "pico_temp"
TOPIC = b"sensor/temperatur"

# ===== Temperatur Sensor =====
sensor = machine.ADC(4)
conversion_factor = 3.3 / 65535

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)

    print("Verbinde WLAN...")
    while not wlan.isconnected():
        time.sleep(1)

    print("WLAN verbunden:", wlan.ifconfig())

def read_temperature():
    raw = sensor.read_u16()
    voltage = raw * conversion_factor
    return 27 - (voltage - 0.706) / 0.001721

# ===== Start =====
connect_wifi()

client = MQTTClient(CLIENT_ID, MQTT_BROKER)
client.connect()
print("MQTT verbunden")

while True:
    temp = read_temperature()
    client.publish(TOPIC, f"{temp:.2f}")
    print("Gesendet:", temp)
    time.sleep(5)
