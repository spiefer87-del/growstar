import datetime
import time

import core.context as ctx

from core.config import config, save_config

from services.energy import (
    refresh_energy_state,
    do_energy_day_reset,
)

from services.shelly import run_failsafe


ENERGY_INTERVAL = 30
FAILSAFE_INTERVAL = 30


def shelly_background_loop():

    while True:

        try:

            now = time.time()

            # =========================================
            # 🛡️ FAILSAFE
            # =========================================

            if now - ctx.last_failsafe_poll >= FAILSAFE_INTERVAL:

                ctx.last_failsafe_poll = now

                with ctx.shelly_lock:
                    run_failsafe()

            # =========================================
            # ⚡ ENERGY POLLING
            # =========================================

            if now - ctx.last_energy_poll >= ENERGY_INTERVAL:

                ctx.last_energy_poll = now
            
                with ctx.shelly_lock:
                    refresh_energy_state()

            # =========================================
            # 📅 AUTO DAY RESET
            # =========================================

            reset_min = int(
                config.get("ENERGY_DAY_RESET_MIN", 0)
            )

            now_dt = datetime.datetime.now()

            now_min = (
                now_dt.hour * 60
                + now_dt.minute
            )

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

        except Exception as e:

            print(
                "❌ Shelly Background Thread Fehler:",
                e
            )

        time.sleep(1)
