# threads/main.py

import time

from core.constants import DB_INTERVAL
from core.runtime import resolve_runtime
from core.devices import DEVICE_NAMES

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
    # falschen Aufruf niemals physische Aktorik erreichen. Während ein nach
    # Neustart persistiertes LIVE auf seinen Preflight wartet, wird der Zyklus
    # sichtbar als ARMING markiert, rechnet intern aber weiterhin shadow-safe.
    if not rt.control_enabled:
        shadow = True

    if rt.control_enabled:
        loop_mode = "live"
    elif getattr(rt, "arming", False) or getattr(rt, "live_requested", False):
        loop_mode = "arming"
    else:
        loop_mode = "shadow" if shadow else "inactive"

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
        ppfd_val = st.live_state.get("light_ppfd")

    # =========================================
    # Datenbank
    # =========================================

    if current_time - st.last_db_write >= DB_INTERVAL:
        st.last_db_write = current_time

        with rt.state_lock:
            temp_target = st.live_state.get("temp_target")
            hum_target = st.live_state.get("hum_target")

        vpd = None
        if temp_val is not None and hum_val is not None:
            vpd = calculate_vpd(temp_val, hum_val)

            with rt.state_lock:
                st.live_state["vpd"] = vpd

        if any(value is not None for value in (temp_val, hum_val, ppfd_val)):
            try:
                insert_measurement(
                    temp=temp_val,
                    temp_target=temp_target,
                    hum=hum_val,
                    hum_target=hum_target,
                    vpd=vpd,
                    ppfd=ppfd_val,
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

    # Alle bekannten Geräte laufen durch dieselbe generische Regelung.
    # Dadurch ist auch eine zukünftige dritte/vierte Station nicht auf die
    # ursprünglichen vier Aktoren beschränkt. Geräte im Modus OFF bleiben AUS.
    for device in DEVICE_NAMES:
        control_device(device, runtime=rt)

    return {
        "tent_id": rt.tent_id,
        "mode": loop_mode,
        "temp": temp_val,
        "hum": hum_val,
        "shadow_outputs": dict(rt.shadow_outputs),
    }


def main_loop(runtime=None, *, shadow=None):
    """Regelkreis für genau eine TentRuntime.

    ``tent_1`` läuft weiterhin produktiv. Zusätzliche Runtimes verwenden
    denselben Thread für SHADOW, ARMING und LIVE. Solange das Runtime-Gate
    ``control_enabled`` geschlossen ist, bleibt physische Aktorik gesperrt.
    """

    rt = resolve_runtime(runtime)

    dynamic_mode = shadow is None

    if rt.control_enabled and shadow is not True:
        print(f"🧠 [{rt.tent_id}] Regelkreis gestartet")
    elif getattr(rt, "live_requested", False):
        print(
            f"🟠 [{rt.tent_id}] ARMING-Regelkreis gestartet "
            "(Hardware-Aktorik bis Preflight gesperrt)"
        )
    else:
        print(
            f"🧪 [{rt.tent_id}] Shadow-Regelkreis gestartet "
            "(Hardware-Aktorik gesperrt)"
        )

    while True:
        # ``shadow=None`` means dynamic mode: after a successful LIVE arming the
        # very same thread automatically changes from shadow-safe calculations
        # to real actuation. No second controller thread is ever started.
        run_control_cycle(
            runtime=rt,
            shadow=None if dynamic_mode else shadow,
        )
        time.sleep(2)
