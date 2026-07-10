# core/sensors.py

import math
import time

import core.state as state

from core.config import config
from core.hardware.manager import manager


_last_sensor_update = 0


# ----------------------------------------------------
# Helfer
# ----------------------------------------------------

def _to_float(value):

    if value is None:

        return None

    try:

        return float(
            value
        )

    except Exception:

        return None


def _find_hardware_device(device_id):

    if not device_id:

        return None

    for device in manager.devices_list():

        if device.id == device_id:

            return device

    return None


def _calculate_vpd(temp, hum):

    if temp is None or hum is None:

        return None

    try:

        svp = 0.6108 * math.exp(
            (17.27 * temp) /
            (temp + 237.3)
        )

        avp = svp * (
            hum / 100.0
        )

        return round(
            svp - avp,
            2
        )

    except Exception:

        return None


def _assignment(sensor_name):

    assignments = config.get(
        "SENSOR_ASSIGNMENTS",
        {}
    )

    return assignments.get(
        sensor_name,
        {
            "source": "legacy"
        }
    )


# ----------------------------------------------------
# Werte aus Hardware-Geräten lesen
# ----------------------------------------------------

def _read_hardware_value(sensor_name, assignment):

    device_id = assignment.get(
        "device_id"
    )

    device = _find_hardware_device(
        device_id
    )

    if device is None:

        return None

    props = device.properties or {}

    prop = assignment.get(
        "property"
    )

    if not prop:

        if sensor_name == "temperature":

            prop = "temperature"

        elif sensor_name == "humidity":

            prop = "humidity"

    return _to_float(
        props.get(
            prop
        )
    )


# ----------------------------------------------------
# Sensor-Zuweisungen anwenden
# ----------------------------------------------------

def apply_sensor_assignments(force=False):
    """
    Wendet Sensor-Zuweisungen auf state.live_state an.

    Wichtig:
    source == "legacy" verändert NICHTS.
    Dadurch bleibt die alte MQTT/Pi-Mikro-Logik aktiv.
    """

    global _last_sensor_update

    now = time.time()

    if (
        not force
        and now - _last_sensor_update < 1
    ):

        return False

    _last_sensor_update = now

    temp_assignment = _assignment(
        "temperature"
    )

    hum_assignment = _assignment(
        "humidity"
    )

    temp_source = temp_assignment.get(
        "source",
        "legacy"
    )

    hum_source = hum_assignment.get(
        "source",
        "legacy"
    )

    changed = False


    # ------------------------------------------------
    # Temperatur
    # ------------------------------------------------

    if temp_source == "hardware_device":

        temp_raw = _read_hardware_value(
            "temperature",
            temp_assignment
        )

        if temp_raw is not None:

            temp_offset = float(
                config.get(
                    "TEMP_OFFSET",
                    0.0
                )
            )

            state.live_state["temp_raw"] = temp_raw
            state.live_state["temp"] = temp_raw + temp_offset

            state.last_temp_raw = temp_raw
            state.last_ds_temp = temp_raw + temp_offset
            state.last_ds_time = now
            state.temp_stale = False

            changed = True


    # ------------------------------------------------
    # Luftfeuchtigkeit
    # ------------------------------------------------

    if hum_source == "hardware_device":

        hum_raw = _read_hardware_value(
            "humidity",
            hum_assignment
        )

        if hum_raw is not None:

            hum_offset = float(
                config.get(
                    "HUM_OFFSET",
                    0.0
                )
            )

            state.live_state["hum_raw"] = hum_raw
            state.live_state["hum"] = hum_raw + hum_offset

            state.last_hum_raw = hum_raw
            state.last_hum = hum_raw + hum_offset
            state.last_dht_time = now
            state.hum_stale = False

            changed = True


    # ------------------------------------------------
    # VPD nur neu berechnen, wenn wir aktiv einen
    # neuen Sensorwert übernommen haben.
    # Bei legacy bleibt alles wie bisher.
    # ------------------------------------------------

    if changed:

        state.live_state["vpd"] = _calculate_vpd(
            state.live_state.get(
                "temp"
            ),
            state.live_state.get(
                "hum"
            )
        )

    state.live_state["sensor_assignments"] = config.get(
        "SENSOR_ASSIGNMENTS",
        {}
    )

    return changed
