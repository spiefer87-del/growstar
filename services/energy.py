"""Multi-station energy polling and accounting for Growstar.

Energy remains controller-polled: one background cycle collects every unique
configured Shelly relay exactly once, then distributes the raw reading to the
owning runtime(s).  Per-station offsets/counters live in the runtime config so
reset state is isolated between tents.
"""

from __future__ import annotations

import datetime
import os
import sqlite3
import threading
import time
from copy import deepcopy

import requests

import core.context as ctx

from core.hardware_assignments import DEVICE_HARDWARE
from core.runtime import (
    get_default_runtime,
    list_runtimes,
    resolve_runtime,
)


DEFAULT_POWER_PRICE = 0.43
ENERGY_REQUEST_TIMEOUT_SEC = 3

# Phase 4M – Historie / Statistik
#
# Die Shellys werden weiterhin ausschließlich im bestehenden 30-s-Energiepoll
# gelesen. Historie und Peaks verwenden nur die bereits eingelesenen Runtime-
# Werte und verursachen deshalb KEINE zusätzlichen Netzwerkrequests.
ENERGY_DB_FILE = os.getenv("GROWSTAR_DB_FILE", "data.db")
ENERGY_HISTORY_SAMPLE_SEC = 120
ENERGY_HISTORY_RETENTION_DAYS = 90
ENERGY_CONTROLLER_ID = "__controller__"

_HISTORY_SCHEMA_LOCK = threading.RLock()
_HISTORY_SCHEMA_READY = False
_HISTORY_LAST_CLEANUP_DAY = None


def _safe_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _relay_value(value):
    if value in (None, ""):
        return None
    try:
        relay = int(value)
    except (TypeError, ValueError):
        return None
    if relay < 0:
        return None
    return relay


def _configured_endpoint(runtime, device):
    meta = DEVICE_HARDWARE.get(device) or {}
    ip_key = meta.get("ip_key")
    relay_key = meta.get("relay_key")
    if not ip_key or not relay_key:
        return None

    host = str(runtime.config.get(ip_key) or "").strip()
    relay = _relay_value(runtime.config.get(relay_key))
    if not host or relay is None:
        return None

    return host, relay


def configured_energy_devices(runtime=None):
    """Return configured energy-capable device endpoints for one runtime."""
    rt = resolve_runtime(runtime)
    result = {}

    for device, meta in DEVICE_HARDWARE.items():
        endpoint = _configured_endpoint(rt, device)
        if endpoint is None:
            continue
        host, relay = endpoint
        result[device] = {
            "label": meta.get("label") or device,
            "host": host,
            "relay": relay,
        }

    return result


def _read_shelly_raw_energy(host, relay, timeout=ENERGY_REQUEST_TIMEOUT_SEC):
    """Read raw power + cumulative energy for one physical relay.

    This function is intentionally independent from station config.  It allows
    refresh_energy_state() to deduplicate physical endpoints before applying
    per-runtime reset offsets.
    """
    try:
        response = requests.get(
            f"http://{host}/rpc/Switch.GetStatus?id={int(relay)}",
            timeout=timeout,
        )
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}"

        data = response.json()
        if not isinstance(data, dict):
            return None, "ungueltige JSON-Antwort"

        power = _safe_float(data.get("apower"))
        total_wh = _safe_float((data.get("aenergy") or {}).get("total"))
        if power is None or total_wh is None:
            return None, "apower/aenergy.total fehlt"

        return {
            "power": round(power, 1),
            "raw_total": round(total_wh / 1000.0, 6),
        }, None

    except Exception as exc:
        return None, str(exc)


def _apply_runtime_offsets(runtime, device, raw_total_kwh, *, today=None):
    """Apply this runtime's total/day offsets to one raw Shelly counter.

    Returns (metrics, config_changed).  Missing TOTAL reset keeps the historic
    behaviour (counter starts at Shelly lifetime zero).  A value of None means
    an explicit reset request and is rebased on the next successful reading.
    """
    rt = resolve_runtime(runtime)
    cfg = rt.config
    today = today or datetime.date.today().isoformat()
    changed = False

    resets = cfg.setdefault("ENERGY_RESET", {})
    offset_total = resets.get(device, 0.0)
    if offset_total is None:
        offset_total = float(raw_total_kwh)
        resets[device] = offset_total
        changed = True

    offset_total = _safe_float(offset_total, 0.0)
    total_kwh = max(0.0, float(raw_total_kwh) - offset_total)

    day_offsets = cfg.setdefault("ENERGY_DAY_OFFSET", {})
    day_entry = day_offsets.get(device)
    if not isinstance(day_entry, dict) or day_entry.get("day") != today:
        day_entry = {
            "day": today,
            "offset": float(raw_total_kwh),
        }
        day_offsets[device] = day_entry
        changed = True

    offset_today = _safe_float(day_entry.get("offset"))
    if offset_today is None:
        offset_today = float(raw_total_kwh)
        day_entry["offset"] = offset_today
        changed = True

    today_kwh = max(0.0, float(raw_total_kwh) - offset_today)

    return {
        "raw_total": round(float(raw_total_kwh), 3),
        "total": round(total_kwh, 3),
        "today": round(today_kwh, 3),
        "offset_total": round(float(offset_total), 3),
        "offset_today": round(float(offset_today), 3),
    }, changed


def get_shelly_energy(ip, relay, device_key, runtime=None, timeout=ENERGY_REQUEST_TIMEOUT_SEC):
    """Backward-compatible single-endpoint helper with runtime-aware offsets."""
    rt = resolve_runtime(runtime)
    raw, error = _read_shelly_raw_energy(ip, relay, timeout=timeout)
    if raw is None:
        if error:
            print(f"❌ [{rt.tent_id}] ENERGY {device_key}: {error}")
        return None

    with rt.energy_lock:
        offset_metrics, changed = _apply_runtime_offsets(
            rt,
            device_key,
            raw["raw_total"],
        )
        result = {
            "power": raw["power"],
            **offset_metrics,
        }

    if changed:
        rt.persist_config()

    return result


def _poll_plan(runtimes):
    """Build endpoint -> owners map so each physical relay is read once."""
    plan = {}
    configured_by_runtime = {}

    for rt in runtimes:
        configured = configured_energy_devices(rt)
        configured_by_runtime[rt.tent_id] = configured
        for device, item in configured.items():
            endpoint = (item["host"], item["relay"])
            plan.setdefault(endpoint, []).append((rt, device, item))

    return plan, configured_by_runtime


def refresh_energy_state(runtimes=None):
    """Poll all loaded stations in one controller-wide energy cycle.

    No UI request performs a Shelly poll.  The background Shelly thread calls
    this function on its existing interval.  Endpoints are deduplicated across
    all runtimes before any network request is made.
    """
    runtimes = list(runtimes) if runtimes is not None else list_runtimes()
    runtimes = [rt for rt in runtimes if getattr(rt, "enabled", True)]

    plan, configured_by_runtime = _poll_plan(runtimes)
    raw_by_endpoint = {}

    for endpoint in plan:
        host, relay = endpoint
        raw_by_endpoint[endpoint] = _read_shelly_raw_energy(host, relay)

    results = {rt.tent_id: {} for rt in runtimes}
    config_changed = {rt.tent_id: False for rt in runtimes}
    now = time.time()
    today = datetime.date.today().isoformat()

    for endpoint, owners in plan.items():
        raw, error = raw_by_endpoint[endpoint]
        for rt, device, item in owners:
            base = {
                "label": item["label"],
                "host": item["host"],
                "relay": item["relay"],
                "available": raw is not None,
                "last_poll": now,
            }

            if raw is None:
                results[rt.tent_id][device] = {
                    **base,
                    "power": None,
                    "raw_total": None,
                    "total": None,
                    "today": None,
                    "error": error or "nicht erreichbar",
                }
                continue

            with rt.energy_lock:
                offset_metrics, changed = _apply_runtime_offsets(
                    rt,
                    device,
                    raw["raw_total"],
                    today=today,
                )
            config_changed[rt.tent_id] = config_changed[rt.tent_id] or changed

            results[rt.tent_id][device] = {
                **base,
                "power": raw["power"],
                **offset_metrics,
                "error": None,
            }

    # Keep configured-but-unplanned runtimes represented by an empty state.
    for rt in runtimes:
        state = results.get(rt.tent_id, {})
        with rt.energy_lock:
            rt.energy_state.clear()
            rt.energy_state.update(state)

        if config_changed.get(rt.tent_id):
            rt.persist_config()

    # ctx.energy_state remains the default-runtime alias for compatibility.
    return {
        "polled_endpoints": len(plan),
        "stations": len(runtimes),
        "configured_devices": sum(len(v) for v in configured_by_runtime.values()),
    }


def _energy_db_connect():
    db = sqlite3.connect(
        ENERGY_DB_FILE,
        timeout=5,
        check_same_thread=False,
    )
    db.execute("PRAGMA busy_timeout = 5000")
    return db


def _ensure_energy_history_schema():
    """Legt die neuen Tabellen idempotent an.

    Absichtlich nicht in db.py: Phase 4M bleibt damit ein isolierter
    Energie-Patch und verändert die bestehende Klima-/Tagebuch-Migration nicht.
    """

    global _HISTORY_SCHEMA_READY

    if _HISTORY_SCHEMA_READY:
        return

    with _HISTORY_SCHEMA_LOCK:
        if _HISTORY_SCHEMA_READY:
            return

        db = _energy_db_connect()
        try:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS energy_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    bucket_ts INTEGER NOT NULL,
                    tent_id TEXT NOT NULL,
                    power_w REAL NOT NULL,
                    today_kwh REAL NOT NULL,
                    UNIQUE(bucket_ts, tent_id)
                )
                """
            )
            db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_energy_history_tent_ts
                ON energy_history (tent_id, ts)
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS energy_daily_peaks (
                    day TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    tent_id TEXT NOT NULL DEFAULT '',
                    device TEXT NOT NULL DEFAULT '',
                    max_power_w REAL NOT NULL,
                    ts INTEGER NOT NULL,
                    PRIMARY KEY (day, scope, tent_id, device)
                )
                """
            )
            db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_energy_daily_peaks_day
                ON energy_daily_peaks (day, scope)
                """
            )
            db.commit()
            _HISTORY_SCHEMA_READY = True
        finally:
            db.close()


def _cleanup_energy_history(now_ts):
    global _HISTORY_LAST_CLEANUP_DAY

    day = datetime.datetime.fromtimestamp(now_ts).date().isoformat()
    if _HISTORY_LAST_CLEANUP_DAY == day:
        return

    cutoff = int(now_ts) - ENERGY_HISTORY_RETENTION_DAYS * 86400
    peak_cutoff_day = (
        datetime.datetime.fromtimestamp(now_ts).date()
        - datetime.timedelta(days=ENERGY_HISTORY_RETENTION_DAYS)
    ).isoformat()

    db = _energy_db_connect()
    try:
        db.execute(
            "DELETE FROM energy_history WHERE ts < ?",
            (cutoff,),
        )
        db.execute(
            "DELETE FROM energy_daily_peaks WHERE day < ?",
            (peak_cutoff_day,),
        )
        db.commit()
        _HISTORY_LAST_CLEANUP_DAY = day
    finally:
        db.close()


def _upsert_daily_peak(db, *, day, scope, power, ts, tent_id="", device=""):
    power = max(0.0, _safe_float(power, 0.0) or 0.0)

    db.execute(
        """
        INSERT INTO energy_daily_peaks (
            day,
            scope,
            tent_id,
            device,
            max_power_w,
            ts
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(day, scope, tent_id, device)
        DO UPDATE SET
            max_power_w = excluded.max_power_w,
            ts = excluded.ts
        WHERE excluded.max_power_w > energy_daily_peaks.max_power_w
        """,
        (
            day,
            str(scope),
            str(tent_id or ""),
            str(device or ""),
            float(power),
            int(ts),
        ),
    )


def record_energy_history(runtimes=None, *, now=None):
    """Persistiert Verlauf + Tagespeaks aus dem bereits vorhandenen Energy-State.

    Aufruf erfolgt direkt NACH refresh_energy_state() im Shelly-Background-
    Thread. Diese Funktion fragt keine Shellys ab und schaltet keine Hardware.

    Verlauf:
      - ein Punkt je Station + Controller pro 2-Minuten-Bucket
      - 90 Tage Aufbewahrung

    Peaks:
      - jeder 30-s-Poll kann das Tagesmaximum aktualisieren
      - Controller, Station und einzelnes Gerät
    """

    runtimes = list(runtimes) if runtimes is not None else list_runtimes()
    runtimes = [rt for rt in runtimes if getattr(rt, "enabled", True)]
    now = int(time.time() if now is None else now)
    day = datetime.datetime.fromtimestamp(now).date().isoformat()
    bucket_ts = now - (now % ENERGY_HISTORY_SAMPLE_SEC)

    station_rows = []
    device_peaks = []
    controller_power = 0.0
    controller_today = 0.0
    controller_available = 0

    for rt in runtimes:
        devices = get_runtime_energy_snapshot(rt)

        station_power = 0.0
        station_today = 0.0
        station_available = 0

        for device, item in devices.items():
            if not item.get("available"):
                continue

            power = max(0.0, _safe_float(item.get("power"), 0.0) or 0.0)
            today_kwh = max(0.0, _safe_float(item.get("today"), 0.0) or 0.0)

            station_power += power
            station_today += today_kwh
            station_available += 1

            device_peaks.append(
                (
                    rt.tent_id,
                    device,
                    power,
                )
            )

        # Keine künstlichen 0-W-Werte erzeugen, wenn eine Station aktuell
        # überhaupt keinen erfolgreichen Energie-Messpunkt besitzt.
        if station_available <= 0:
            continue

        station_rows.append(
            (
                rt.tent_id,
                round(station_power, 1),
                round(station_today, 6),
            )
        )
        controller_power += station_power
        controller_today += station_today
        controller_available += station_available

    if controller_available <= 0:
        return {
            "success": True,
            "recorded": False,
            "reason": "no_available_energy_points",
        }

    _ensure_energy_history_schema()

    db = _energy_db_connect()
    try:
        # Verlauf: UPSERT im 2-Minuten-Bucket. Der letzte Poll innerhalb des
        # Buckets gewinnt, wodurch die DB auch bei 30-s-Poll klein bleibt.
        for tent_id, power, today_kwh in station_rows:
            db.execute(
                """
                INSERT INTO energy_history (
                    ts,
                    bucket_ts,
                    tent_id,
                    power_w,
                    today_kwh
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(bucket_ts, tent_id)
                DO UPDATE SET
                    ts = excluded.ts,
                    power_w = excluded.power_w,
                    today_kwh = excluded.today_kwh
                """,
                (
                    now,
                    bucket_ts,
                    tent_id,
                    power,
                    today_kwh,
                ),
            )

        db.execute(
            """
            INSERT INTO energy_history (
                ts,
                bucket_ts,
                tent_id,
                power_w,
                today_kwh
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(bucket_ts, tent_id)
            DO UPDATE SET
                ts = excluded.ts,
                power_w = excluded.power_w,
                today_kwh = excluded.today_kwh
            """,
            (
                now,
                bucket_ts,
                ENERGY_CONTROLLER_ID,
                round(controller_power, 1),
                round(controller_today, 6),
            ),
        )

        # Tagespeaks bleiben genauer als der Verlauf: jeder Energie-Poll darf
        # den Maximalwert aktualisieren.
        _upsert_daily_peak(
            db,
            day=day,
            scope="controller",
            power=controller_power,
            ts=now,
        )

        for tent_id, power, _today_kwh in station_rows:
            _upsert_daily_peak(
                db,
                day=day,
                scope="station",
                tent_id=tent_id,
                power=power,
                ts=now,
            )

        for tent_id, device, power in device_peaks:
            _upsert_daily_peak(
                db,
                day=day,
                scope="device",
                tent_id=tent_id,
                device=device,
                power=power,
                ts=now,
            )

        db.commit()
    finally:
        db.close()

    _cleanup_energy_history(now)

    return {
        "success": True,
        "recorded": True,
        "bucket_ts": bucket_ts,
        "stations": len(station_rows),
        "controller_power": round(controller_power, 1),
    }


def _read_daily_peak_rows(day):
    # Read-only: kein Schema während Regression/API-Lesezugriff erzwingen.
    # Nach dem ersten produktiven History-Poll existieren die Tabellen.
    if not os.path.exists(ENERGY_DB_FILE):
        return []

    db = _energy_db_connect()
    try:
        try:
            return db.execute(
                """
                SELECT scope, tent_id, device, max_power_w, ts
                FROM energy_daily_peaks
                WHERE day = ?
                """,
                (day,),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    finally:
        db.close()


def get_daily_energy_peaks(*, day=None):
    day = day or datetime.date.today().isoformat()
    result = {
        "day": day,
        "controller": None,
        "stations": {},
        "devices": {},
    }

    for scope, tent_id, device, power, ts in _read_daily_peak_rows(day):
        item = {
            "power": round(float(power), 1),
            "ts": int(ts),
        }

        if scope == "controller":
            result["controller"] = item
        elif scope == "station":
            result["stations"][tent_id] = item
        elif scope == "device":
            result["devices"].setdefault(tent_id, {})[device] = item

    return result


_HISTORY_RANGES = {
    "today": {
        "seconds": None,
        "bucket": 300,
        "label": "Heute",
    },
    "24h": {
        "seconds": 24 * 3600,
        "bucket": 300,
        "label": "24 Stunden",
    },
    "7d": {
        "seconds": 7 * 86400,
        "bucket": 1800,
        "label": "7 Tage",
    },
    "30d": {
        "seconds": 30 * 86400,
        "bucket": 7200,
        "label": "30 Tage",
    },
}


def _history_window(range_key, now):
    spec = _HISTORY_RANGES.get(range_key)
    if spec is None:
        raise ValueError(
            "range muss today, 24h, 7d oder 30d sein"
        )

    now_dt = datetime.datetime.fromtimestamp(now)

    if range_key == "today":
        start_dt = now_dt.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        start = int(start_dt.timestamp())
    else:
        start = int(now - int(spec["seconds"]))

    return {
        "range": range_key,
        "label": spec["label"],
        "start": start,
        "end": int(now),
        "bucket": int(spec["bucket"]),
    }


def get_energy_history(range_key="today", *, now=None):
    """Aggregierte Leistungs-Historie ohne Hardwarezugriff."""

    now = int(time.time() if now is None else now)
    window = _history_window(
        str(range_key or "today").lower(),
        now,
    )

    rows = []

    if os.path.exists(ENERGY_DB_FILE):
        db = _energy_db_connect()
        try:
            try:
                rows = db.execute(
                    """
                    SELECT
                        tent_id,
                        CAST(ts / ? AS INTEGER) * ? AS grouped_ts,
                        AVG(power_w) AS avg_power,
                        MAX(today_kwh) AS today_kwh
                    FROM energy_history
                    WHERE ts BETWEEN ? AND ?
                    GROUP BY tent_id, grouped_ts
                    ORDER BY grouped_ts ASC
                    """,
                    (
                        window["bucket"],
                        window["bucket"],
                        window["start"],
                        window["end"],
                    ),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
        finally:
            db.close()

    by_tent = {}
    for tent_id, ts, avg_power, today_kwh in rows:
        by_tent.setdefault(tent_id, []).append({
            "ts": int(ts),
            "power": round(float(avg_power or 0.0), 1),
            "today": round(float(today_kwh or 0.0), 4),
        })

    runtime_names = {
        rt.tent_id: rt.name
        for rt in list_runtimes()
        if getattr(rt, "enabled", True)
    }

    series = []
    controller_points = by_tent.pop(ENERGY_CONTROLLER_ID, [])
    series.append({
        "tent_id": ENERGY_CONTROLLER_ID,
        "name": "Gesamtanlage",
        "controller": True,
        "points": controller_points,
    })

    for tent_id, name in runtime_names.items():
        series.append({
            "tent_id": tent_id,
            "name": name,
            "controller": False,
            "points": by_tent.pop(tent_id, []),
        })

    # Historische Daten einer inzwischen deaktivierten Station nicht verlieren.
    for tent_id, points in sorted(by_tent.items()):
        series.append({
            "tent_id": tent_id,
            "name": tent_id,
            "controller": False,
            "points": points,
        })

    return {
        "success": True,
        **window,
        "sample_interval_sec": ENERGY_HISTORY_SAMPLE_SEC,
        "retention_days": ENERGY_HISTORY_RETENTION_DAYS,
        "series": series,
    }


def get_runtime_energy_snapshot(runtime=None):
    rt = resolve_runtime(runtime)
    with rt.energy_lock:
        return deepcopy(rt.energy_state)


def _runtime_mode(rt):
    if getattr(rt, "control_enabled", False):
        return "live"
    if getattr(rt, "arming", False):
        return "arming"
    if getattr(rt, "shadow_enabled", False):
        return "shadow"
    return getattr(rt, "loop_mode", None) or "inactive"


def _energy_totals(devices, price):
    power = 0.0
    today = 0.0
    total = 0.0
    available = 0

    for item in devices.values():
        if not item.get("available"):
            continue
        available += 1
        power += _safe_float(item.get("power"), 0.0) or 0.0
        today += _safe_float(item.get("today"), 0.0) or 0.0
        total += _safe_float(item.get("total"), 0.0) or 0.0

    return {
        "power": round(power, 1),
        "today": round(today, 3),
        "total": round(total, 3),
        "cost_today": round(today * price, 2),
        "cost_total": round(total * price, 2),
        "available_devices": available,
        "configured_devices": len(devices),
    }


def get_energy_settings():
    """Controller-wide accounting settings intentionally live in tent_1 config."""
    rt = get_default_runtime()
    price = _safe_float(rt.config.get("POWER_PRICE"), DEFAULT_POWER_PRICE)
    reset_min = rt.config.get("ENERGY_DAY_RESET_MIN", 0)
    try:
        reset_min = int(reset_min)
    except (TypeError, ValueError):
        reset_min = 0
    reset_min = max(0, min(1439, reset_min))

    return {
        "power_price": round(float(price), 4),
        "day_reset_min": reset_min,
        "last_day_reset": rt.config.get("ENERGY_LAST_DAY_RESET"),
    }


def update_energy_settings(data):
    if not isinstance(data, dict):
        raise TypeError("Energie-Einstellungen muessen ein JSON-Objekt sein")

    rt = get_default_runtime()
    changed = []

    if "power_price" in data or "POWER_PRICE" in data:
        raw = data.get("power_price", data.get("POWER_PRICE"))
        price = _safe_float(raw)
        if price is None or price < 0 or price > 10:
            raise ValueError("Strompreis muss zwischen 0 und 10 EUR/kWh liegen")
        rt.config["POWER_PRICE"] = round(price, 4)
        changed.append("POWER_PRICE")

    if "day_reset_min" in data or "ENERGY_DAY_RESET_MIN" in data:
        raw = data.get("day_reset_min", data.get("ENERGY_DAY_RESET_MIN"))
        try:
            reset_min = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("Reset-Zeit muss eine Minute des Tages sein") from exc
        if not 0 <= reset_min <= 1439:
            raise ValueError("Reset-Zeit muss zwischen 0 und 1439 liegen")
        rt.config["ENERGY_DAY_RESET_MIN"] = reset_min
        changed.append("ENERGY_DAY_RESET_MIN")

    if changed:
        rt.persist_config()

    return {
        "settings": get_energy_settings(),
        "changed_keys": changed,
    }


def build_energy_overview(runtimes=None):
    runtimes = list(runtimes) if runtimes is not None else list_runtimes()
    runtimes = [rt for rt in runtimes if getattr(rt, "enabled", True)]
    settings = get_energy_settings()
    price = float(settings["power_price"])
    daily_peaks = get_daily_energy_peaks()

    stations = []
    global_devices = []

    for rt in runtimes:
        devices = get_runtime_energy_snapshot(rt)
        totals = _energy_totals(devices, price)

        station_peak = daily_peaks["stations"].get(rt.tent_id)

        for device, item in devices.items():
            peak = daily_peaks["devices"].get(rt.tent_id, {}).get(device)
            item["max_power_today"] = peak["power"] if peak else None
            item["max_power_today_ts"] = peak["ts"] if peak else None

        station = {
            "tent_id": rt.tent_id,
            "name": rt.name,
            "runtime_mode": _runtime_mode(rt),
            "control_enabled": bool(getattr(rt, "control_enabled", False)),
            "devices": devices,
            "totals": totals,
            "max_power_today": station_peak["power"] if station_peak else None,
            "max_power_today_ts": station_peak["ts"] if station_peak else None,
        }
        stations.append(station)

        for device, item in devices.items():
            if not item.get("available"):
                continue
            global_devices.append({
                "tent_id": rt.tent_id,
                "tent_name": rt.name,
                "device": device,
                "label": item.get("label") or device,
                "power": _safe_float(item.get("power"), 0.0) or 0.0,
                "today": _safe_float(item.get("today"), 0.0) or 0.0,
                "total": _safe_float(item.get("total"), 0.0) or 0.0,
            })

    controller_totals = {
        "power": round(sum(s["totals"]["power"] for s in stations), 1),
        "today": round(sum(s["totals"]["today"] for s in stations), 3),
        "total": round(sum(s["totals"]["total"] for s in stations), 3),
        "cost_today": round(sum(s["totals"]["cost_today"] for s in stations), 2),
        "cost_total": round(sum(s["totals"]["cost_total"] for s in stations), 2),
        "configured_devices": sum(s["totals"]["configured_devices"] for s in stations),
        "available_devices": sum(s["totals"]["available_devices"] for s in stations),
    }

    top_today_candidates = [item for item in global_devices if item["today"] > 0]
    top_power_candidates = [item for item in global_devices if item["power"] > 0]
    top_today = max(top_today_candidates, key=lambda x: x["today"], default=None)
    top_power = max(top_power_candidates, key=lambda x: x["power"], default=None)

    controller_peak = daily_peaks.get("controller")

    max_device_peak_today = None
    for rt in runtimes:
        for device, peak in daily_peaks["devices"].get(rt.tent_id, {}).items():
            candidate = {
                "tent_id": rt.tent_id,
                "tent_name": rt.name,
                "device": device,
                "label": (DEVICE_HARDWARE.get(device) or {}).get("label") or device,
                "power": peak["power"],
                "ts": peak["ts"],
            }
            if (
                max_device_peak_today is None
                or candidate["power"] > max_device_peak_today["power"]
            ):
                max_device_peak_today = candidate

    for station in stations:
        if controller_totals["today"] > 0:
            station["today_share_pct"] = round(
                station["totals"]["today"] / controller_totals["today"] * 100.0,
                1,
            )
        else:
            station["today_share_pct"] = 0.0

        if controller_totals["power"] > 0:
            station["power_share_pct"] = round(
                station["totals"]["power"] / controller_totals["power"] * 100.0,
                1,
            )
        else:
            station["power_share_pct"] = 0.0

    return {
        "success": True,
        "generated_at": time.time(),
        "last_poll": ctx.last_energy_poll or None,
        "settings": settings,
        "totals": {
            **controller_totals,
            "max_power_today": controller_peak["power"] if controller_peak else None,
            "max_power_today_ts": controller_peak["ts"] if controller_peak else None,
        },
        "statistics": {
            "station_count": len(stations),
            "top_today": top_today,
            "top_power": top_power,
            "max_power_today": controller_peak,
            "max_device_peak_today": max_device_peak_today,
            "peak_day": daily_peaks.get("day"),
        },
        "stations": stations,
    }


def _validate_reset_device(runtime, device):
    if device not in DEVICE_HARDWARE:
        raise ValueError(f"Unbekanntes Energiegeraet: {device}")

    # Reset is allowed for a currently configured endpoint or an existing
    # energy entry.  This prevents arbitrary config keys from being created.
    configured = configured_energy_devices(runtime)
    state = get_runtime_energy_snapshot(runtime)
    if device not in configured and device not in state:
        raise ValueError(f"{device} ist in {runtime.tent_id} nicht zugeordnet")


def reset_runtime_total(runtime=None, device=None):
    rt = resolve_runtime(runtime)
    if device is not None:
        _validate_reset_device(rt, device)

    with rt.energy_lock:
        state = rt.energy_state
        targets = [device] if device is not None else list(configured_energy_devices(rt))
        resets = rt.config.setdefault("ENERGY_RESET", {})

        for key in targets:
            entry = state.get(key) or {}
            raw = _safe_float(entry.get("raw_total"))
            resets[key] = raw if raw is not None else None
            if key in state and raw is not None:
                state[key]["total"] = 0.0
                state[key]["offset_total"] = round(raw, 3)

    rt.persist_config()
    return targets


def reset_runtime_today(runtime=None, device=None, *, today=None):
    rt = resolve_runtime(runtime)
    if device is not None:
        _validate_reset_device(rt, device)

    today = today or datetime.date.today().isoformat()

    with rt.energy_lock:
        state = rt.energy_state
        targets = [device] if device is not None else list(configured_energy_devices(rt))
        offsets = rt.config.setdefault("ENERGY_DAY_OFFSET", {})

        for key in targets:
            entry = state.get(key) or {}
            raw = _safe_float(entry.get("raw_total"))
            offsets[key] = {
                "day": today,
                "offset": raw,
            } if raw is not None else None

            if key in state and raw is not None:
                state[key]["today"] = 0.0
                state[key]["offset_today"] = round(raw, 3)

    rt.persist_config()
    return targets


def reset_total_all_runtimes():
    changed = {}
    for rt in list_runtimes():
        if not getattr(rt, "enabled", True):
            continue
        targets = reset_runtime_total(rt)
        changed[rt.tent_id] = targets
    return changed


def reset_today_all_runtimes(*, today=None):
    changed = {}
    for rt in list_runtimes():
        if not getattr(rt, "enabled", True):
            continue
        targets = reset_runtime_today(rt, today=today)
        changed[rt.tent_id] = targets
    return changed


def do_energy_day_reset():
    """Reset today's offsets for every loaded station in one scheduled action."""
    today = datetime.date.today().isoformat()
    runtimes = [rt for rt in list_runtimes() if getattr(rt, "enabled", True)]

    configured_count = sum(len(configured_energy_devices(rt)) for rt in runtimes)
    available_count = sum(
        1
        for rt in runtimes
        for item in get_runtime_energy_snapshot(rt).values()
        if item.get("available") and item.get("raw_total") is not None
    )

    # No configured energy hardware: nothing to reset, but the day is complete.
    if configured_count == 0:
        default_rt = get_default_runtime()
        default_rt.config["ENERGY_LAST_DAY_RESET"] = today
        default_rt.persist_config()
        return True

    # Configured hardware exists but no reading is available yet.  Do not mark
    # the reset complete; the background thread will retry after polling.
    if available_count == 0:
        return False

    reset_today_all_runtimes(today=today)

    default_rt = get_default_runtime()
    default_rt.config["ENERGY_LAST_DAY_RESET"] = today
    default_rt.persist_config()

    print(f"📅 ENERGY: Auto-Tagesreset fuer {len(runtimes)} Station(en) durchgefuehrt")
    return True


def get_today_kwh(device_key, raw_total_kwh, runtime=None):
    """Backward-compatible helper used by older callers."""
    rt = resolve_runtime(runtime)
    with rt.energy_lock:
        metrics, changed = _apply_runtime_offsets(
            rt,
            device_key,
            float(raw_total_kwh),
        )
    if changed:
        rt.persist_config()
    return metrics["today"]
