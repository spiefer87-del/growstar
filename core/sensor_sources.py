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
    ppfd=None,
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

        if ppfd is not None:
            source["ppfd"] = float(ppfd)

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
        elif sensor_name == "ppfd":
            field = "ppfd"
        elif sensor_name == "outside_temperature":
            field = "temperature"
        elif sensor_name == "outside_humidity":
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
    ppfd_raw, ppfd_source, ppfd_assignment = _read_assigned_value(
        "ppfd",
        runtime=rt,
    )
    outside_temp_raw, outside_temp_source, outside_temp_assignment = (
        _read_assigned_value(
            "outside_temperature",
            runtime=rt,
        )
    )
    outside_hum_raw, outside_hum_source, outside_hum_assignment = (
        _read_assigned_value(
            "outside_humidity",
            runtime=rt,
        )
    )

    if ppfd_raw is None:
        assignments = cfg.get("SENSOR_ASSIGNMENTS", {})
        for sensor_name in ("temperature", "humidity"):
            assignment = (assignments or {}).get(sensor_name) or {}
            source_id = str(assignment.get("source_id") or "").strip()
            if not source_id.startswith("spiderfarmer:"):
                continue
            candidate = get_sensor_source(source_id)
            if not isinstance(candidate, dict) or candidate.get("ppfd") is None:
                continue
            try:
                ppfd_raw = float(candidate.get("ppfd"))
            except (TypeError, ValueError):
                continue
            ppfd_source = candidate
            ppfd_assignment = {
                "source_id": source_id,
                "field": "ppfd",
                "label": candidate.get("label") or source_id,
            }
            break

    now = time.time()
    temp_last_seen = _source_last_seen(temp_source)
    hum_last_seen = _source_last_seen(hum_source)
    ppfd_last_seen = _source_last_seen(ppfd_source)
    outside_temp_last_seen = _source_last_seen(outside_temp_source)
    outside_hum_last_seen = _source_last_seen(outside_hum_source)
    temp_fresh = temp_raw is not None and _source_is_fresh(temp_source, now)
    hum_fresh = hum_raw is not None and _source_is_fresh(hum_source, now)
    ppfd_fresh = ppfd_raw is not None and _source_is_fresh(ppfd_source, now)
    outside_temp_fresh = (
        outside_temp_raw is not None
        and _source_is_fresh(outside_temp_source, now)
    )
    outside_hum_fresh = (
        outside_hum_raw is not None
        and _source_is_fresh(outside_hum_source, now)
    )

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

        if ppfd_fresh:
            st.live_state["light_ppfd"] = ppfd_raw
            st.live_state["light_ppfd_source"] = {
                "source_id": ppfd_assignment.get("source_id"),
                "label": (
                    ppfd_assignment.get("label")
                    or (ppfd_source or {}).get("label")
                    or ppfd_assignment.get("source_id")
                ),
                "last_seen": ppfd_last_seen,
            }
            changed = True
        else:
            st.live_state.pop("light_ppfd", None)
            st.live_state.pop("light_ppfd_source", None)

        # Außenquellen besitzen eigene Kalibrierwerte. Die Innen-Offsets
        # bleiben dadurch ausschließlich den Regelquellen im Zelt zugeordnet.
        # Der VPD-Kern rechnet mit den korrigierten Außenwerten; RAW bleibt für
        # die nachvollziehbare Kalibrierung separat sichtbar.
        if outside_temp_fresh:
            outside_temp_offset = float(
                cfg.get("OUTSIDE_TEMP_OFFSET", 0.0)
            )
            outside_temp = float(outside_temp_raw) + outside_temp_offset

            st.live_state["outside_temp_raw"] = float(outside_temp_raw)
            st.live_state["outside_temp"] = outside_temp
            st.live_state["outside_temp_source"] = {
                "source_id": outside_temp_assignment.get("source_id"),
                "label": (
                    outside_temp_assignment.get("label")
                    or (outside_temp_source or {}).get("label")
                    or outside_temp_assignment.get("source_id")
                ),
                "last_seen": outside_temp_last_seen,
            }
            changed = True
        else:
            st.live_state["outside_temp_raw"] = None
            st.live_state["outside_temp"] = None
            st.live_state["outside_temp_source"] = None

        if outside_hum_fresh:
            outside_hum_offset = float(
                cfg.get("OUTSIDE_HUM_OFFSET", 0.0)
            )
            outside_hum = float(outside_hum_raw) + outside_hum_offset

            st.live_state["outside_hum_raw"] = float(outside_hum_raw)
            st.live_state["outside_hum"] = outside_hum
            st.live_state["outside_hum_source"] = {
                "source_id": outside_hum_assignment.get("source_id"),
                "label": (
                    outside_hum_assignment.get("label")
                    or (outside_hum_source or {}).get("label")
                    or outside_hum_assignment.get("source_id")
                ),
                "last_seen": outside_hum_last_seen,
            }
            changed = True
        else:
            st.live_state["outside_hum_raw"] = None
            st.live_state["outside_hum"] = None
            st.live_state["outside_hum_source"] = None

        st.live_state["vpd"] = _calculate_vpd(
            st.live_state.get("temp"),
            st.live_state.get("hum"),
        )

        st.live_state["sensor_assignments"] = cfg.get(
            "SENSOR_ASSIGNMENTS",
            {},
        )

    return changed
