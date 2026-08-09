# threads/main.py

import time

from core.constants import DB_INTERVAL
from core.runtime import resolve_runtime

from db import insert_measurement

from core.helpers import calculate_vpd

from core.control import (
    update_temperature_setpoint,
    update_humidity_setpoint,
    control_device,
)

from core.sensor_sources import apply_sensor_assignments

from core.ramp import (
    check_ramp_schedule,
    update_ramp,
)

from services.sensor import mark_stale_sensors


def main_loop(runtime=None):
    """Regelkreis für genau eine TentRuntime.

    ``runtime=None`` bleibt vollständig kompatibel zum bisherigen Aufruf und
    verwendet automatisch ``tent_1``. Ein zweites Zelt wird in Phase 2 noch
    nicht produktiv gestartet; der Loop ist aber bereits runtime-fähig.
    """

    rt = resolve_runtime(runtime)
    st = rt.state

    print(f"🧠 [{rt.tent_id}] Regelkreis gestartet")

    while True:
        now = time.time()

        # =========================================
        # Sensor-Zuweisung anwenden
        # =========================================

        apply_sensor_assignments(runtime=rt)

        # =========================================
        # Sollwerte / Profil / Rampe
        # =========================================

        check_ramp_schedule(runtime=rt)

        if st.ramp_active:
            update_ramp(runtime=rt)

        update_temperature_setpoint(runtime=rt)
        update_humidity_setpoint(runtime=rt)

        # =========================================
        # Sensor Health
        # =========================================

        mark_stale_sensors(runtime=rt)

        # =========================================
        # Snapshot
        # =========================================

        with rt.state_lock:
            temp_val = st.live_state.get("temp")
            hum_val = st.live_state.get("hum")

        # =========================================
        # Datenbank
        # =========================================

        if now - st.last_db_write >= DB_INTERVAL:
            st.last_db_write = now

            with rt.state_lock:
                temp_target = st.live_state.get("temp_target")
                hum_target = st.live_state.get("hum_target")

            if temp_val is not None and hum_val is not None:
                vpd = calculate_vpd(temp_val, hum_val)

                with rt.state_lock:
                    st.live_state["vpd"] = vpd

                try:
                    insert_measurement(
                        temp=temp_val,
                        temp_target=temp_target,
                        hum=hum_val,
                        hum_target=hum_target,
                        vpd=vpd,
                        tent_id=rt.tent_id,
                    )
                except Exception as exc:
                    print(
                        f"❌ [{rt.tent_id}] DB insert_measurement Fehler:",
                        exc,
                    )

        # =========================================
        # Regelung
        # =========================================

        control_device("fan", runtime=rt)
        control_device("vent", runtime=rt)
        control_device("heating", runtime=rt)
        control_device("light", runtime=rt)

        time.sleep(2)
