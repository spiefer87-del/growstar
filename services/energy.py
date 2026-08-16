"""Multi-station energy polling and accounting for Growstar.

Energy remains controller-polled: one background cycle collects every unique
configured Shelly relay exactly once, then distributes the raw reading to the
owning runtime(s).  Per-station offsets/counters live in the runtime config so
reset state is isolated between tents.
"""

from __future__ import annotations

import datetime
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

    stations = []
    global_devices = []

    for rt in runtimes:
        devices = get_runtime_energy_snapshot(rt)
        totals = _energy_totals(devices, price)

        station = {
            "tent_id": rt.tent_id,
            "name": rt.name,
            "runtime_mode": _runtime_mode(rt),
            "control_enabled": bool(getattr(rt, "control_enabled", False)),
            "devices": devices,
            "totals": totals,
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
        "totals": controller_totals,
        "statistics": {
            "station_count": len(stations),
            "top_today": top_today,
            "top_power": top_power,
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
