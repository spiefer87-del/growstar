# threads/blu.py

import time
import threading

from core.config import config

from services.hardware import hardware


_thread_started = False


def _interval():

    try:

        return int(
            config.get(
                "SENSOR_UPDATE_INTERVAL_SEC",
                60
            )
        )

    except Exception:

        return 60


def _blu_devices():

    devices = []

    try:

        all_devices = hardware.devices()

    except Exception:

        return devices

    for device in all_devices:

        props = device.properties or {}

        if device.type != "sensor":

            continue

        if props.get("protocol") != "bthome":

            continue

        if not (
            props.get("paired")
            or props.get("bthome_device_id")
            or props.get("bthome_device_key")
            or props.get("paired_gateways")
        ):

            continue

        devices.append(
            device
        )

    return devices


def blu_loop():

    print(
        "🔵 BLU Sensor-Thread gestartet"
    )

    while True:

        try:

            devices = _blu_devices()

            for device in devices:

                try:

                    print(
                        "🔵 Aktualisiere BLU Sensor:",
                        device.id
                    )

                    hardware.read_ble_sensor_values(
                        device.id,
                        listen=False
                    )

                except Exception as e:

                    print(
                        "BLU Sensor Update Fehler:",
                        device.id,
                        e
                    )

        except Exception as e:

            print(
                "BLU Sensor Thread Fehler:",
                e
            )

        time.sleep(
            max(
                15,
                _interval()
            )
        )


def start_blu_thread():

    global _thread_started

    if _thread_started:

        return

    _thread_started = True

    thread = threading.Thread(
        target=blu_loop,
        daemon=True
    )

    thread.start()
