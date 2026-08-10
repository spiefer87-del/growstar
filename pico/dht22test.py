from machine import Pin
import dht
import time

sensor = dht.DHT22(Pin(16))

while True:
    sensor.measure()
    print(sensor.temperature(), sensor.humidity())
    time.sleep(5)
