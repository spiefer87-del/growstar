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


def run_control_cycle(runtime=None, *, now=None, shadow=None):
    """Führt genau einen vollständigen Regelzyklus einer TentRuntime aus.

    Die Extraktion aus ``main_loop`` macht den Mehrzelt-Regelkreis testbar,
    ohne Threads starten zu müssen. ``shadow`` dient nur der Statusanzeige;
    die eigentliche Hardware-Sicherheitsbarriere liegt zusätzlich in
    ``core.actuators`` und hängt ausschließlich an ``control_enabled``.
    """

    rt = resolve_runtime(runtime)
    st = rt.state

    if shadow is None:
        shadow = not rt.control_enabled

    # Eine Runtime ohne Hardwarefreigabe darf auch bei einem versehentlich
    # falschen Aufruf nur als Shadow laufen.
    if not rt.control_enabled:
        shadow = True

    loop_mode = "shadow" if shadow else "live"
    rt.mark_loop(loop_mode)

    current_time = time.time() if now is None else float(now)

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

    if current_time - st.last_db_write >= DB_INTERVAL:
        st.last_db_write = current_time

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

    return {
        "tent_id": rt.tent_id,
        "mode": loop_mode,
        "temp": temp_val,
        "hum": hum_val,
        "shadow_outputs": dict(rt.shadow_outputs),
    }


def main_loop(runtime=None, *, shadow=None):
    """Regelkreis für genau eine TentRuntime.

    ``tent_1`` läuft weiterhin produktiv. Zusätzliche Runtimes werden in
    Phase 3B nur mit ``shadow=True`` gestartet. Selbst wenn dieser Parameter
    falsch gesetzt würde, verhindert ``control_enabled=False`` in der Runtime
    jede physische Aktorik.
    """

    rt = resolve_runtime(runtime)

    if shadow is None:
        shadow = not rt.control_enabled

    if not rt.control_enabled:
        shadow = True

    if shadow:
        print(
            f"🧪 [{rt.tent_id}] Shadow-Regelkreis gestartet "
            "(Hardware-Aktorik gesperrt)"
        )
    else:
        print(f"🧠 [{rt.tent_id}] Regelkreis gestartet")

    while True:
        run_control_cycle(runtime=rt, shadow=shadow)
        time.sleep(2)
