import datetime
import time

import core.context as ctx

from core.config import config, save_config
from core.constants import ENERGY_DEVICES

from services.energy import (
    get_shelly_energy,
    do_energy_day_reset,
)

from services.shelly import (
    failsafe_check,
)


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

                    failsafe_check(
                        "heating",
                        "IP_HEATING",
                        "RELAY_HEATING"
                    )

                    failsafe_check(
                        "fan",
                        "IP_FAN",
                        "RELAY_FAN"
                    )

                    failsafe_check(
                        "light",
                        "IP_LIGHT",
                        "RELAY_LIGHT"
                    )

                    failsafe_check(
                        "vent",
                        "IP_VENT",
                        "RELAY_VENT"
                    )

                    # später aktivieren
                    # failsafe_check(...)
                    # irrigation
                    # humidifier
                    # dehumidifier
                    # light2
                    # vent2

            # =========================================
            # ⚡ ENERGY POLLING
            # =========================================

            if now - ctx.last_energy_poll >= ENERGY_INTERVAL:

                ctx.last_energy_poll = now

                tmp = {}

                with ctx.shelly_lock:

                    for name, (ip_key, relay_key) in ENERGY_DEVICES.items():

                        ip = config.get(ip_key)
                        relay = config.get(relay_key)

                        if not ip or relay is None:
                            continue

                        energy = get_shelly_energy(
                            ip,
                            relay,
                            name,
                            timeout=2
                        )

                        if energy:
                            tmp[name] = energy

                with ctx.energy_lock:
                    ctx.energy_state.clear()
                    ctx.energy_state.update(tmp)

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
