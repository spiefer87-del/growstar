# threads/blu.py

import time
import threading

from core.config import config
from core.hardware.vivosun import PROTOCOL as VIVOSUN_PROTOCOL
from core.hardware.visibility import fresh_mqtt_vivosun_addresses
from core.sensor_sources import list_sensor_sources

from services.hardware import hardware


_thread_started = False
_next_updates = {}


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


def _vivosun_interval():
    try:
        return max(
            5,
            int(config.get("VIVOSUN_UPDATE_INTERVAL_SEC", 10)),
        )
    except Exception:
        return 10


def _device_interval(device):
    props = device.properties or {}
    if props.get("protocol") == VIVOSUN_PROTOCOL:
        return _vivosun_interval()
    return max(15, _interval())


def _blu_devices():

    devices = []

    try:
        mqtt_vivosun_addresses = fresh_mqtt_vivosun_addresses(
            list_sensor_sources()
        )
    except Exception:
        mqtt_vivosun_addresses = set()

    try:

        all_devices = hardware.devices()

    except Exception:

        return devices

    for device in all_devices:

        props = device.properties or {}

        if device.type != "sensor":

            continue

        protocol = props.get("protocol")

        if protocol not in {"bthome", VIVOSUN_PROTOCOL}:

            continue

        if protocol == VIVOSUN_PROTOCOL:
            compact_address = str(props.get("addr") or "").replace(":", "").lower()
            if compact_address in mqtt_vivosun_addresses:
                continue
            if props.get("registered") and props.get("addr"):
                devices.append(device)
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
            now = time.monotonic()
            active_ids = {device.id for device in devices}

            for device_id in tuple(_next_updates):
                if device_id not in active_ids:
                    _next_updates.pop(device_id, None)

            for device in devices:

                if now < _next_updates.get(device.id, 0):
                    continue

                _next_updates[device.id] = now + _device_interval(device)

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

        time.sleep(1)


def start_blu_thread():

    global _thread_started

    if _thread_started:

        return

    _thread_started = True

    thread = threading.Thread(
        name="growstar-blu",
        target=blu_loop,
        daemon=True
    )

    thread.start()
