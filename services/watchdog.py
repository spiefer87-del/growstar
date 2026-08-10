# services/watchdog.py

import datetime
import time

import core.context as ctx

from core.watchdog_health import build_watchdog_snapshot


WATCHDOG_INTERVAL = 5
WARN_REPEAT_SEC = 60
CONFIG_WARN_REPEAT_SEC = 300

_last_warning = {}


def log_event(msg, level="INFO"):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {level}: {msg}\n"

    try:
        with open(ctx.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as exc:
        print("❌ Log write error:", exc)


def _rate_limited_log(key, message, *, level="WARN", repeat=WARN_REPEAT_SEC, now=None):
    now = time.time() if now is None else float(now)
    last = _last_warning.get(key, 0)
    if now - last < repeat:
        return False

    log_event(message, level)
    _last_warning[key] = now
    return True


def watchdog_cycle(*, now=None):
    """Führt genau einen read-only Watchdog-Zyklus aus.

    Die Funktion ist separat testbar und schaltet niemals Hardware.
    """

    now = time.time() if now is None else float(now)
    ctx.WATCHDOG_LAST_LOOP = now

    snapshot = build_watchdog_snapshot(now=now)

    for station in snapshot["stations"]:
        tent_id = station["id"]

        if station["loop"]["stale"]:
            age = station["loop"]["age"]
            detail = "noch kein Heartbeat" if age is None else f"{int(age)}s"
            _rate_limited_log(
                (tent_id, "loop"),
                f"[{tent_id}] REGELKREIS stale: {detail}",
                now=now,
            )

        for sensor_key, label in (("temperature", "TEMP"), ("humidity", "HUM")):
            sensor = station[sensor_key]
            if not sensor["configured"]:
                continue
            if not sensor["stale"]:
                continue

            age = sensor["age"]
            detail = "keine Daten" if age is None else f"{int(age)}s keine Daten"
            _rate_limited_log(
                (tent_id, sensor_key),
                f"[{tent_id}] {label} Sensor stale: {detail}",
                now=now,
            )

        if not station["config"]["ok"]:
            _rate_limited_log(
                (tent_id, "config"),
                f"[{tent_id}] CONFIG ungültig: " + "; ".join(station["config"]["issues"]),
                repeat=CONFIG_WARN_REPEAT_SEC,
                now=now,
            )

    # Bestehenden Energie-Hinweis beibehalten, jedoch controllerweit nur einmal.
    if snapshot["controller"]["energy"]["stale"]:
        _rate_limited_log(
            ("controller", "energy"),
            "ENERGY: keine Daten (energy_state leer)",
            now=now,
        )

    return snapshot


def watchdog_loop():
    while True:
        try:
            watchdog_cycle()
        except Exception as exc:
            log_event(f"Watchdog Fehler: {exc}", "ERROR")

        time.sleep(WATCHDOG_INTERVAL)
