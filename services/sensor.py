# services/sensor.py

import time

from core.runtime import resolve_runtime
from core.helpers import calculate_vpd
from core.constants import SENSOR_TIMEOUT
from core.actuators import set_heating, set_fan


# =========================================
# Sensor Update (Legacy-Direktpfad)
# =========================================

def update_temperature(temp_raw, runtime=None):
    rt = resolve_runtime(runtime)
    st = rt.state
    cfg = rt.config

    now = time.time()
    temp = round(temp_raw + float(cfg.get("TEMP_OFFSET", 0.0)), 2)

    with rt.state_lock:
        st.last_temp_raw = temp_raw
        # Legacy-Verhalten beibehalten: interner Direktpfad speichert hier
        # weiterhin den Rohwert; der Live-Wert enthält den Offset.
        st.last_ds_temp = temp_raw
        st.last_ds_time = now
        st.temp_stale = False

        st.live_state["temp_raw"] = temp_raw
        st.live_state["temp"] = temp


def update_humidity(hum_raw, runtime=None):
    rt = resolve_runtime(runtime)
    st = rt.state
    cfg = rt.config

    now = time.time()
    hum = round(hum_raw + float(cfg.get("HUM_OFFSET", 0.0)), 2)

    with rt.state_lock:
        st.last_hum_raw = hum_raw
        # Legacy-Verhalten beibehalten (siehe update_temperature).
        st.last_hum = hum_raw
        st.last_dht_time = now
        st.hum_stale = False

        st.live_state["hum_raw"] = hum_raw
        st.live_state["hum"] = hum


# =========================================
# Sensor Health
# =========================================

def mark_stale_sensors(runtime=None):
    rt = resolve_runtime(runtime)
    st = rt.state

    now = time.time()

    with rt.state_lock:
        temp_age = now - st.last_ds_time
        hum_age = now - st.last_dht_time

    if temp_age > SENSOR_TIMEOUT:
        if not st.temp_stale:
            print(
                f"⚠️ [{rt.tent_id}] TEMP SENSOR STALE "
                f"({int(temp_age)}s ohne Daten)"
            )

        st.temp_stale = True

        with rt.state_lock:
            st.live_state["temp"] = None
            st.live_state["temp_raw"] = None
            st.live_state["vpd"] = None

        set_heating(False, "(TEMP SENSOR STALE)", runtime=rt)

    else:
        if st.temp_stale:
            print(f"✅ [{rt.tent_id}] TEMP SENSOR wieder da")
        st.temp_stale = False

    if hum_age > SENSOR_TIMEOUT:
        if not st.hum_stale:
            print(
                f"⚠️ [{rt.tent_id}] HUM SENSOR STALE "
                f"({int(hum_age)}s ohne Daten)"
            )

        st.hum_stale = True

        with rt.state_lock:
            st.live_state["hum"] = None
            st.live_state["hum_raw"] = None
            st.live_state["vpd"] = None

        set_fan(False, "(HUM SENSOR STALE)", runtime=rt)

    else:
        if st.hum_stale:
            print(f"✅ [{rt.tent_id}] HUM SENSOR wieder da")
        st.hum_stale = False

    update_vpd(runtime=rt)


# =========================================
# VPD
# =========================================

def update_vpd(runtime=None):
    rt = resolve_runtime(runtime)
    st = rt.state

    with rt.state_lock:
        temp = st.live_state.get("temp")
        hum = st.live_state.get("hum")

        if temp is None or hum is None:
            st.live_state["vpd"] = None
            return

        st.live_state["vpd"] = calculate_vpd(temp, hum)
