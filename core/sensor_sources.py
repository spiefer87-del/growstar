# core/sensor_sources.py

import math
import time

import core.context as ctx
import core.state as controller_state

from core.runtime import resolve_runtime
from core.constants import SENSOR_TIMEOUT


# ----------------------------------------------------
# Architektur Phase 2
# ----------------------------------------------------
# Sensorquellen gehören zum Controller, nicht zu einem einzelnen Zelt.
# MQTT/Bluetooth/Hardware dürfen daher weiterhin ohne Tent-ID Quellen melden.
# Erst die SENSOR_ASSIGNMENTS einer TentRuntime entscheiden, welche Quelle für
# Temperatur bzw. Feuchte dieses Zeltes verwendet wird.


def update_sensor_source(
    source_id,
    label=None,
    source_type=None,
    temperature=None,
    humidity=None,
    battery=None,
    rssi=None,
    raw=None,
):
    if not source_id:
        return None

    now = time.time()

    with ctx.state_lock:
        sources = controller_state.live_state.setdefault("sensor_sources", {})
        source = sources.get(source_id, {})

        source["id"] = source_id
        source["label"] = label or source.get("label") or source_id
        source["type"] = source_type or source.get("type") or "unknown"
        source["last_seen"] = now
        source["online"] = True

        if temperature is not None:
            source["temperature"] = float(temperature)

        if humidity is not None:
            source["humidity"] = float(humidity)

        if battery is not None:
            source["battery"] = battery

        if rssi is not None:
            source["rssi"] = rssi

        if raw is not None:
            source["raw"] = raw

        sources[source_id] = source
        return dict(source)


# ----------------------------------------------------
# Quelle lesen
# ----------------------------------------------------

def get_sensor_source(source_id):
    if not source_id:
        return None

    with ctx.state_lock:
        source = controller_state.live_state.get("sensor_sources", {}).get(source_id)
        return dict(source) if source else None


def list_sensor_sources():
    with ctx.state_lock:
        return [
            dict(source)
            for source in controller_state.live_state.get(
                "sensor_sources",
                {},
            ).values()
        ]


# ----------------------------------------------------
# Rechnen
# ----------------------------------------------------

def _calculate_vpd(temp, hum):
    if temp is None or hum is None:
        return None

    try:
        svp = 0.6108 * math.exp((17.27 * temp) / (temp + 237.3))
        avp = svp * (hum / 100.0)
        return round(svp - avp, 2)
    except Exception:
        return None


def _read_assignment(sensor_name, runtime=None):
    rt = resolve_runtime(runtime)
    assignments = rt.config.get("SENSOR_ASSIGNMENTS", {})
    return assignments.get(sensor_name, {})


def _read_assigned_value(sensor_name, runtime=None):
    assignment = _read_assignment(sensor_name, runtime=runtime)

    source_id = assignment.get("source_id")
    field = assignment.get("field")

    if not field:
        if sensor_name == "temperature":
            field = "temperature"
        elif sensor_name == "humidity":
            field = "humidity"

    source = get_sensor_source(source_id)

    if source is None:
        return None, None, assignment

    value = source.get(field)
    if value is None:
        return None, source, assignment

    try:
        return float(value), source, assignment
    except Exception:
        return None, source, assignment


# ----------------------------------------------------
# Zentrale Anwendung für Regelung
# ----------------------------------------------------

def _source_last_seen(source):
    try:
        return float((source or {}).get("last_seen") or 0)
    except (TypeError, ValueError):
        return 0.0


def _source_is_fresh(source, now=None):
    last_seen = _source_last_seen(source)
    if last_seen <= 0:
        return False

    current = time.time() if now is None else float(now)
    return (current - last_seen) <= SENSOR_TIMEOUT


def apply_sensor_assignments(runtime=None):
    """Überträgt frische Controller-Sensorquellen in den State eines Zeltes.

    Der Zeitstempel der Quelle ist die einzige Wahrheit für Sensor-Frische.
    Ein Main-Loop darf eine alte Quelle deshalb weder erneut als frisch
    markieren noch den letzten Empfangszeitpunkt künstlich nach vorne setzen.
    """

    rt = resolve_runtime(runtime)
    st = rt.state
    cfg = rt.config

    temp_raw, temp_source, temp_assignment = _read_assigned_value(
        "temperature",
        runtime=rt,
    )
    hum_raw, hum_source, hum_assignment = _read_assigned_value(
        "humidity",
        runtime=rt,
    )

    now = time.time()
    temp_last_seen = _source_last_seen(temp_source)
    hum_last_seen = _source_last_seen(hum_source)
    temp_fresh = temp_raw is not None and _source_is_fresh(temp_source, now)
    hum_fresh = hum_raw is not None and _source_is_fresh(hum_source, now)

    changed = False

    with rt.state_lock:
        # Den echten Empfangszeitpunkt auch dann übernehmen, wenn die Quelle
        # bereits stale ist. mark_stale_sensors() kann dadurch korrekt über
        # den Ausfall entscheiden, ohne dass alte Werte kurz wieder im UI
        # auftauchen.
        if temp_last_seen > 0:
            st.last_ds_time = temp_last_seen

        if hum_last_seen > 0:
            st.last_dht_time = hum_last_seen

        if temp_fresh:
            temp_offset = float(cfg.get("TEMP_OFFSET", 0.0))
            temp = temp_raw + temp_offset

            st.live_state["temp_raw"] = temp_raw
            st.live_state["temp"] = temp

            st.last_temp_raw = temp_raw
            st.last_ds_temp = temp
            st.temp_stale = False

            st.live_state["temp_source"] = (
                temp_assignment.get("label")
                or (temp_source or {}).get("label")
                or temp_assignment.get("source_id")
            )

            changed = True

        if hum_fresh:
            hum_offset = float(cfg.get("HUM_OFFSET", 0.0))
            hum = hum_raw + hum_offset

            st.live_state["hum_raw"] = hum_raw
            st.live_state["hum"] = hum

            st.last_hum_raw = hum_raw
            st.last_hum = hum
            st.hum_stale = False

            st.live_state["hum_source"] = (
                hum_assignment.get("label")
                or (hum_source or {}).get("label")
                or hum_assignment.get("source_id")
            )

            changed = True

        st.live_state["vpd"] = _calculate_vpd(
            st.live_state.get("temp"),
            st.live_state.get("hum"),
        )

        st.live_state["sensor_assignments"] = cfg.get(
            "SENSOR_ASSIGNMENTS",
            {},
        )

    return changed
