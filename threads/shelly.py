import datetime
import time

import core.context as ctx

from core.config import config
from core.runtime import list_runtimes

from services.energy import (
    refresh_energy_state,
    record_energy_history,
    do_energy_day_reset,
)
from services.shelly import run_failsafe
from services.safety import run_all_live_safety


ENERGY_INTERVAL = 30
FAILSAFE_INTERVAL = 30
SAFETY_INTERVAL = 2


def _run_all_live_failsafes():
    """Runs the existing Shelly failsafe for every ACTUALLY armed LIVE runtime."""

    for runtime in list_runtimes():
        if not runtime.enabled or not runtime.control_enabled:
            continue
        # During an explicit LIVE -> SHADOW safe-stop, the transition service
        # owns the relays. The periodic failsafe must not race it and switch a
        # relay back to the previous controller setpoint.
        if getattr(runtime, "disarming", False):
            continue
        run_failsafe(runtime=runtime)


def shelly_background_loop():
    last_safety_poll = 0.0

    while True:
        try:
            now = time.time()

            # =========================================
            # 🚨 STATIONS-SAFETY – unabhaengig vom Regelkreis
            # =========================================
            if now - last_safety_poll >= SAFETY_INTERVAL:
                last_safety_poll = now

                with ctx.shelly_lock:
                    run_all_live_safety(now=now, enforce=True)

            # =========================================
            # 🛡️ RELAY-SYNC FAILSAFE – multi-station
            # =========================================
            if now - ctx.last_failsafe_poll >= FAILSAFE_INTERVAL:
                ctx.last_failsafe_poll = now

                with ctx.shelly_lock:
                    _run_all_live_failsafes()

            # =========================================
            # ⚡ ENERGY POLLING – controllerweit, stationsbezogen verteilt
            # =========================================
            # A single poll cycle iterates all loaded runtimes, deduplicates
            # physical (host, relay) endpoints and writes each result only into
            # the owning runtime.energy_state. UI/API reads never poll Shellys.
            if now - ctx.last_energy_poll >= ENERGY_INTERVAL:
                ctx.last_energy_poll = now

                with ctx.shelly_lock:
                    refresh_energy_state()
                    # Phase 4M: keine zusätzlichen Shelly-Reads. Verlauf und
                    # Peaks werden ausschließlich aus dem soeben aktualisierten
                    # Runtime-Energie-State persistiert.
                    record_energy_history()

            # =========================================
            # 📅 AUTO DAY RESET – one schedule, all loaded stations
            # =========================================
            reset_min = int(config.get("ENERGY_DAY_RESET_MIN", 0))
            now_dt = datetime.datetime.now()
            now_min = now_dt.hour * 60 + now_dt.minute
            today = now_dt.date().isoformat()

            if (
                now_min >= reset_min
                and config.get("ENERGY_LAST_DAY_RESET") != today
            ):
                with ctx.shelly_lock:
                    reset_done = do_energy_day_reset()

                if reset_done:
                    print(
                        f"📅 AUTO RESET abgeschlossen "
                        f"({now_dt.hour:02d}:{now_dt.minute:02d})"
                    )

        except Exception as exc:
            print("❌ Shelly Background Thread Fehler:", exc)

        time.sleep(1)
