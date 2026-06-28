
import time

import core.state as state
import core.context as ctx

from core.config import config
from core.helpers import calculate_vpd
from core.constants import SENSOR_TIMEOUT

from core.actuators import (
    set_heating,
    set_fan,
)


# =========================================
# Sensor Update
# =========================================

def update_temperature(temp_raw):

    now = time.time()

    temp = round(
        temp_raw + float(config.get("TEMP_OFFSET", 0.0)),
        2
    )

    with ctx.state_lock:

        state.last_ds_temp = temp_raw
        state.last_ds_time = now

        state.live_state["temp_raw"] = temp_raw
        state.live_state["temp"] = temp


def update_humidity(hum_raw):

    now = time.time()

    hum = round(
        hum_raw + float(config.get("HUM_OFFSET", 0.0)),
        2
    )

    with ctx.state_lock:

        state.last_hum = hum_raw
        state.last_dht_time = now

        state.live_state["hum_raw"] = hum_raw
        state.live_state["hum"] = hum


# =========================================
# Sensor Health
# =========================================

def mark_stale_sensors():

    now = time.time()

    with ctx.state_lock:
        temp_age = now - state.last_ds_time
        hum_age = now - state.last_dht_time

    # =========================
    # Temperatur
    # =========================

    if temp_age > SENSOR_TIMEOUT:

        if not state.temp_stale:
            print(f"⚠️ TEMP SENSOR STALE ({int(temp_age)}s ohne Daten)")

        state.temp_stale = True

        state.live_state["temp"] = None
        state.live_state["temp_raw"] = None
        state.live_state["vpd"] = None

        set_heating(False, "(TEMP SENSOR STALE)")

    else:

        if state.temp_stale:
            print("✅ TEMP SENSOR wieder da")

        state.temp_stale = False

    # =========================
    # Luftfeuchte
    # =========================

    if hum_age > SENSOR_TIMEOUT:

        if not state.hum_stale:
            print(f"⚠️ HUM SENSOR STALE ({int(hum_age)}s ohne Daten)")

        state.hum_stale = True

        state.live_state["hum"] = None
        state.live_state["hum_raw"] = None
        state.live_state["vpd"] = None

        set_fan(False, "(HUM SENSOR STALE)")

    else:

        if state.hum_stale:
            print("✅ HUM SENSOR wieder da")

        state.hum_stale = False

    update_vpd()


# =========================================
# VPD
# =========================================

def update_vpd():

    temp = state.live_state.get("temp")
    hum = state.live_state.get("hum")

    if temp is None or hum is None:

        state.live_state["vpd"] = None
        return

    state.live_state["vpd"] = calculate_vpd(
        temp,
        hum,
    )
