import time

import core.state as state
import core.context as ctx

from core.constants import DB_INTERVAL

from db import insert_measurement

from core.helpers import calculate_vpd

from core.control import (
    update_temperature_setpoint,
    update_humidity_setpoint,
    control_device,
)

from core.ramp import (
    check_ramp_schedule,
    update_ramp,
)

from services.sensor import (
    mark_stale_sensors,
)


def main_loop():

    while True:

        now = time.time()

        # =========================================
        # Sollwerte aktualisieren
        # =========================================

        update_temperature_setpoint()
        update_humidity_setpoint()

        check_ramp_schedule()

        # =========================================
        # Rampe
        # =========================================

        if state.ramp_active:
            update_ramp()

        # =========================================
        # Sensor Health
        # =========================================

        mark_stale_sensors()

        # =========================================
        # Snapshot
        # =========================================

        with ctx.state_lock:

            temp_val = state.live_state.get("temp")
            hum_val = state.live_state.get("hum")

        # =========================================
        # Datenbank
        # =========================================

        if now - state.last_db_write >= DB_INTERVAL:

            state.last_db_write = now

            with ctx.state_lock:

                temp_target = state.live_state.get("temp_target")
                hum_target = state.live_state.get("hum_target")

            if (
                temp_val is not None
                and hum_val is not None
            ):

                vpd = calculate_vpd(
                    temp_val,
                    hum_val,
                )

                with ctx.state_lock:
                    state.live_state["vpd"] = vpd

                try:

                    insert_measurement(
                        temp=temp_val,
                        temp_target=temp_target,
                        hum=hum_val,
                        hum_target=hum_target,
                        vpd=vpd,
                    )

                except Exception as e:

                    print(
                        "❌ DB insert_measurement Fehler:",
                        e
                    )

        # =========================================
        # Regelung
        # =========================================

        control_device("fan")
        control_device("vent")
        control_device("heating")
        control_device("light")

        time.sleep(2)
