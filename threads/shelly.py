import datetime
import time

import core.context as ctx

from core.config import config, save_config
from core.runtime import list_runtimes

from services.energy import (
    refresh_energy_state,
    do_energy_day_reset,
)
from services.shelly import run_failsafe


ENERGY_INTERVAL = 30
FAILSAFE_INTERVAL = 30


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
    while True:
        try:
            now = time.time()

            # =========================================
            # 🛡️ FAILSAFE – now multi-station
            # =========================================
            if now - ctx.last_failsafe_poll >= FAILSAFE_INTERVAL:
                ctx.last_failsafe_poll = now

                with ctx.shelly_lock:
                    _run_all_live_failsafes()

            # =========================================
            # ⚡ ENERGY POLLING
            # =========================================
            # Energy is still the legacy/default-station subsystem. Phase 4H
            # deliberately changes only hardware-control safety here.
            if now - ctx.last_energy_poll >= ENERGY_INTERVAL:
                ctx.last_energy_poll = now

                with ctx.shelly_lock:
                    refresh_energy_state()

            # =========================================
            # 📅 AUTO DAY RESET
            # =========================================
            reset_min = int(config.get("ENERGY_DAY_RESET_MIN", 0))
            now_dt = datetime.datetime.now()
            now_min = now_dt.hour * 60 + now_dt.minute
            today = now_dt.date().isoformat()

            if (
                now_min >= reset_min
                and config.get("ENERGY_LAST_DAY_RESET") != today
            ):
                print(
                    f"📅 AUTO RESET "
                    f"({now_dt.hour:02d}:{now_dt.minute:02d})"
                )

                with ctx.shelly_lock:
                    do_energy_day_reset()

                config["ENERGY_LAST_DAY_RESET"] = today
                save_config(config)

        except Exception as exc:
            print("❌ Shelly Background Thread Fehler:", exc)

        time.sleep(1)
