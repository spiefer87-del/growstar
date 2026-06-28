import time

from services.mqtt import (
    create_client,
    MQTT_BROKER,
    MQTT_PORT
)

def mqtt_thread():

    while True:

        try:

            print("📡 MQTT Thread startet...")

            client = create_client()

            client.connect(
                MQTT_BROKER,
                MQTT_PORT,
                keepalive=30
            )

            client.loop_forever(
                retry_first_connection=True
            )

        except Exception as e:

            print("❌ MQTT Thread Fehler:", e)

        print("🔁 MQTT reconnect in 5s")

        time.sleep(5)
