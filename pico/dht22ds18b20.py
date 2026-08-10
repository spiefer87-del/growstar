# Bibliotheken laden
from machine import Pin
from time import sleep, sleep_ms
from onewire import OneWire
from ds18x20 import DS18X20
from dht import DHT11, DHT22

# 1 Sekunde auf den Sensor warten
sleep(1)



# Initialisierung GPIO und DHT22
print('DHT22 initialisieren')
dht22_sensor = DHT22(Pin(15, Pin.IN, Pin.PULL_UP))

# Initialisierung GPIO, OneWire und DS18B20
print('DS18B20 über OneWire initialisieren')
ds_sensor = DS18X20(OneWire(Pin(16)))
devices = ds_sensor.scan()
print()

# Wiederholung (Endlos-Schleife)
while True:
    # DHT22
    dht22_sensor.measure()
    temp = dht22_sensor.temperature()
    print('  DHT22 Sensor:', temp, '°C')
    # DS18B20
    ds_sensor.convert_temp()
    sleep_ms(750)
    for device in devices:
        print('DS18B20 Sensor:', ds_sensor.read_temp(device), '°C')
    sleep(5)
    print()