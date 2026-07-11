# core/sensor_sources.py

import time
import math

import core.state as state
import core.context as ctx

from core.config import config


# ----------------------------------------------------
# Quelle speichern
# ----------------------------------------------------

def update_sensor_source(
    source_id,
    label=None,
    source_type=None,
    temperature=None,
    humidity=None,
    battery=None,
    rssi=None,
    raw=None
):

    if not source_id:

        return None

    now = time.time()

    with ctx.state_lock:

        sources = state.live_state.setdefault(
            "sensor_sources",
            {}
        )

        source = sources.get(
            source_id,
            {}
        )

        source["id"] = source_id
        source["label"] = label or source.get("label") or source_id
        source["type"] = source_type or source.get("type") or "unknown"
        source["last_seen"] = now
        source["online"] = True

        if temperature is not None:

            source["temperature"] = float(
                temperature
            )

        if humidity is not None:

            source["humidity"] = float(
                humidity
            )

        if battery is not None:

            source["battery"] = battery

        if rssi is not None:

            source["rssi"] = rssi

        if raw is not None:

            source["raw"] = raw

        sources[source_id] = source

        return source


# ----------------------------------------------------
# Quelle lesen
# ----------------------------------------------------

def get_sensor_source(source_id):

    if not source_id:

        return None

    return state.live_state.get(
        "sensor_sources",
        {}
    ).get(
        source_id
    )


def list_sensor_sources():

    return list(
        state.live_state.get(
            "sensor_sources",
            {}
        ).values()
    )


# ----------------------------------------------------
# Rechnen
# ----------------------------------------------------

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


def _read_assignment(sensor_name):

    assignments = config.get(
        "SENSOR_ASSIGNMENTS",
        {}
    )

    return assignments.get(
        sensor_name,
        {}
    )


def _read_assigned_value(sensor_name):

    assignment = _read_assignment(
        sensor_name
    )

    source_id = assignment.get(
        "source_id"
    )

    field = assignment.get(
        "field"
    )

    if not field:

        if sensor_name == "temperature":

            field = "temperature"

        elif sensor_name == "humidity":

            field = "humidity"

    source = get_sensor_source(
        source_id
    )

    if source is None:

        return None, None, assignment

    value = source.get(
        field
    )

    if value is None:

        return None, source, assignment

    try:

        return float(value), source, assignment

    except Exception:

        return None, source, assignment


# ----------------------------------------------------
# Zentrale Anwendung für Regelung
# ----------------------------------------------------

def apply_sensor_assignments():

    changed = False

    with ctx.state_lock:

        temp_raw, temp_source, temp_assignment = _read_assigned_value(
            "temperature"
        )

        hum_raw, hum_source, hum_assignment = _read_assigned_value(
            "humidity"
        )

        if temp_raw is not None:

            temp_offset = float(
                config.get(
                    "TEMP_OFFSET",
                    0.0
                )
            )

            temp = temp_raw + temp_offset

            state.live_state["temp_raw"] = temp_raw
            state.live_state["temp"] = temp

            state.last_temp_raw = temp_raw
            state.last_ds_temp = temp
            state.last_ds_time = time.time()
            state.temp_stale = False

            state.live_state["temp_source"] = (
                temp_assignment.get("label")
                or temp_source.get("label")
                or temp_assignment.get("source_id")
            )

            changed = True

        if hum_raw is not None:

            hum_offset = float(
                config.get(
                    "HUM_OFFSET",
                    0.0
                )
            )

            hum = hum_raw + hum_offset

            state.live_state["hum_raw"] = hum_raw
            state.live_state["hum"] = hum

            state.last_hum_raw = hum_raw
            state.last_hum = hum
            state.last_dht_time = time.time()
            state.hum_stale = False

            state.live_state["hum_source"] = (
                hum_assignment.get("label")
                or hum_source.get("label")
                or hum_assignment.get("source_id")
            )

            changed = True

        state.live_state["vpd"] = _calculate_vpd(
            state.live_state.get("temp"),
            state.live_state.get("hum")
        )

        state.live_state["sensor_assignments"] = config.get(
            "SENSOR_ASSIGNMENTS",
            {}
        )

    return changed
