import time
import core.state as state
import core.context as ctx

from core.constants import SENSOR_TIMEOUT


def log_event(msg, level="INFO"):
    import datetime

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {level}: {msg}\n"

    try:
        with open(ctx.LOG_FILE, "a") as f:
            f.write(line)
    except Exception as e:
        print("❌ Log write error:", e)


def watchdog_loop():

    last_warn_temp = 0
    last_warn_hum = 0
    last_warn_energy = 0

    WATCHDOG_INTERVAL = 5

    while True:

        try:

            now = time.time()

            with ctx.state_lock:
                ds_age = now - state.last_ds_time
                dht_age = now - state.last_dht_time

            if state.last_ds_time and ds_age > SENSOR_TIMEOUT:

                if now - last_warn_temp > 60:
                    log_event(
                        f"TEMP Sensor stale: {int(ds_age)}s keine Daten",
                        "WARN"
                    )
                    last_warn_temp = now

            if state.last_dht_time and dht_age > SENSOR_TIMEOUT:

                if now - last_warn_hum > 60:
                    log_event(
                        f"HUM Sensor stale: {int(dht_age)}s keine Daten",
                        "WARN"
                    )
                    last_warn_hum = now

            with ctx.energy_lock:
                snapshot = dict(ctx.energy_state)

            if not snapshot:

                if now - last_warn_energy > 60:
                    log_event(
                        "ENERGY: keine Daten (energy_state leer)",
                        "WARN"
                    )
                    last_warn_energy = now

        except Exception as e:

            log_event(
                f"Watchdog Fehler: {e}",
                "ERROR"
            )

        time.sleep(WATCHDOG_INTERVAL)
