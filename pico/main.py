import time
import machine
import network
import dht
import onewire
import ds18x20

from umqttsimple import MQTTClient
from config import (
    SSID,
    PASSWORD,
    MQTT_BROKER,
    MQTT_PORT,
    CLIENT_ID,
    TOPIC_DHT22,
    TOPIC_DS18B20,
    PUBLISH_INTERVAL_SEC,
)


# =========================
# SICHERER START
# =========================
time.sleep(3)
print("Pico W startet (DHT22 + DS18B20)")

# SAFE MODE: GP0 -> GND
safe_pin = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)
if safe_pin.value() == 0:
    print("SAFE MODE aktiv")
    while True:
        time.sleep(1)


# =========================
# SENSOR SETUP
# =========================
dht_sensor = dht.DHT22(machine.Pin(15))

ow = onewire.OneWire(machine.Pin(16))
ds_sensor = ds18x20.DS18X20(ow)
roms = ds_sensor.scan()

if not roms:
    print("❌ Kein DS18B20 gefunden")
else:
    print("✅ DS18B20 gefunden:", len(roms))


# =========================
# WLAN & MQTT
# =========================
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

mqtt_client = None
wifi_connected = False
mqtt_connected = False


def connect_wifi():
    global wifi_connected

    if wlan.isconnected():
        wifi_connected = True
        return True

    print("WLAN verbinden...")
    wlan.connect(SSID, PASSWORD)

    timeout = 20
    while not wlan.isconnected() and timeout > 0:
        time.sleep(1)
        timeout -= 1

    wifi_connected = wlan.isconnected()

    if wifi_connected:
        print("WLAN OK:", wlan.ifconfig())
        time.sleep(2)
    else:
        print("WLAN FEHLGESCHLAGEN")

    return wifi_connected


def connect_mqtt():
    global mqtt_client, mqtt_connected

    try:
        mqtt_client = MQTTClient(
            CLIENT_ID,
            MQTT_BROKER,
            port=MQTT_PORT,
            keepalive=60,
        )
        mqtt_client.connect()
        mqtt_connected = True
        print("MQTT verbunden")
        return True

    except Exception as exc:
        mqtt_client = None
        mqtt_connected = False
        print("MQTT Fehler:", exc)
        return False


# =========================
# START
# =========================
connect_wifi()
connect_mqtt()


# =========================
# HAUPTSCHLEIFE
# =========================
while True:
    try:
        if not wlan.isconnected():
            wifi_connected = False
            mqtt_connected = False
            connect_wifi()

        if wifi_connected and not mqtt_connected:
            connect_mqtt()

        if mqtt_connected:
            # DHT22
            dht_sensor.measure()
            t_dht = dht_sensor.temperature()
            h_dht = dht_sensor.humidity()

            if t_dht is not None and h_dht is not None:
                msg_dht = '{"temp":%.1f,"hum":%.1f}' % (t_dht, h_dht)
                mqtt_client.publish(TOPIC_DHT22, msg_dht)
                print("📤 DHT22:", msg_dht)

            # DS18B20
            if roms:
                ds_sensor.convert_temp()
                time.sleep_ms(750)
                t_ds = ds_sensor.read_temp(roms[0])

                msg_ds = '{"temp":%.1f}' % t_ds
                mqtt_client.publish(TOPIC_DS18B20, msg_ds)
                print("📤 DS18B20:", msg_ds)

    except Exception as exc:
        print("Loop-Fehler:", exc)
        mqtt_connected = False
        mqtt_client = None

    time.sleep(PUBLISH_INTERVAL_SEC)
