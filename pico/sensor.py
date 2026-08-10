import network
import requests
import time
import machine

headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)"
            }
# WLAN Zugangsdaten
SSID = 'UPCE1EBAD8'
PASSWORD = '5jnnratwJuy87'

# Ziel-URL des HTTP-Servers (z.B. ein lokaler Webserver oder ein Cloud-Dienst)
SERVER_URL = "http://192.168.0.101/api/data"

def connect_wlan():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('Verbinde mit WLAN...')
        wlan.connect(SSID, PASSWORD)
        
        # Warten auf Verbindung (max. 10 Sekunden)
        attempt = 0
        while not wlan.isconnected() and attempt < 10:
            time.sleep(1)
            attempt += 1
            
    if wlan.isconnected():
        print('Verbunden! IP:', wlan.ifconfig()[0])
    else:
        print('Verbindung fehlgeschlagen.')

def get_internal_temp():
    # Liest den internen Temperatursensor des Pico aus
    sensor_temp = machine.ADC(4)
    conversion_factor = 3.3 / (65535)
    reading = sensor_temp.read_u16() * conversion_factor
    temperature = 27 - (reading - 0.706) / 0.001721
    return round(temperature, 2)

def send_data(temp):
    data = {'temperature': temp}
    response = None
    try:
        response = requests.post(SERVER_URL, json=data, headers= headers) # Timeout hinzufügen
        time.sleep(1)
        print("Status:", response.status_code)
    except OSError as e:
        print("Netzwerkfehler:", e)
    finally:
        if response:
            response.close() # Ganz wichtig!

# Hauptprogramm
connect_wlan()

while True:
    temp = get_internal_temp()
    print(f"Aktuelle Temperatur: {temp}°C")
    send_data(temp)
    
    # Warte 60 Sekunden bis zur nächsten Messung
    time.sleep(60)
