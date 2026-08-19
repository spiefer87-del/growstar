"""Zentrale Growstar-Alarm-Engine auf Basis des Watchdog-Snapshots.

Keine Aktorsteuerung, keine Shelly-Requests und keine direkten Telegram-Requests.
Die Engine liest ausschließlich vorhandene Health-Daten und legt Nachrichten in
die getrennte Notification-Queue.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import threading
import time

from core.runtime import get_runtime
from core.watchdog_health import build_watchdog_snapshot
from services.notification_settings import load_notification_settings
from services.notifications import enqueue_notification


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTANCE_DIR = PROJECT_ROOT / "instance"
STATE_FILE = INSTANCE_DIR / "alarm_state.json"

ALARM_INTERVAL_SEC = 5
STARTUP_GRACE_SEC = 90
HARDWARE_FAILURE_THRESHOLD = 2
MAX_HISTORY = 200

_STATE_LOCK = threading.RLock()
_ENGINE_STARTED_AT = None
_LAST_CYCLE_AT = None
_LAST_ERROR = None
_STATE_LOADED = False
_ACTIVE = {}
_HISTORY = []


def _atomic_save():
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    temp = STATE_FILE.with_suffix(".tmp")
    payload = {
        "active": _ACTIVE,
        "history": _HISTORY[-MAX_HISTORY:],
    }

    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())

    os.chmod(temp, 0o600)
    os.replace(temp, STATE_FILE)
    os.chmod(STATE_FILE, 0o600)


def _ensure_loaded():
    global _STATE_LOADED, _ACTIVE, _HISTORY

    if _STATE_LOADED:
        return

    with _STATE_LOCK:
        if _STATE_LOADED:
            return

        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                active = data.get("active")
                history = data.get("history")
                if isinstance(active, dict):
                    _ACTIVE = active
                if isinstance(history, list):
                    _HISTORY = history[-MAX_HISTORY:]
            except Exception:
                _ACTIVE = {}
                _HISTORY = []

        _STATE_LOADED = True


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _candidate(key, rule, severity, title, detail, *, station=None, station_name=None):
    return {
        "key": key,
        "rule": rule,
        "severity": severity,
        "title": title,
        "detail": detail,
        "station": station,
        "station_name": station_name,
    }


def _station_limits(station_id):
    try:
        runtime = get_runtime(station_id)
    except Exception:
        return {}

    cfg = runtime.config
    return {
        "min_temp": _number(cfg.get("MIN_TEMP")),
        "max_temp": _number(cfg.get("MAX_TEMP")),
        "min_hum": _number(cfg.get("MIN_HUM")),
        "max_hum": _number(cfg.get("MAX_HUM")),
    }


def extract_alarm_candidates(snapshot):
    candidates = {}

    for station in snapshot.get("stations") or []:
        station_id = str(station.get("id") or "station")
        station_name = str(station.get("name") or station_id)

        if not station.get("enabled"):
            continue

        loop = station.get("loop") or {}
        if loop.get("stale"):
            age = loop.get("age")
            detail = (
                "Regelkreis hat noch keinen Heartbeat."
                if age is None
                else f"Seit {int(float(age))} Sekunden kein frischer Regelkreis-Heartbeat."
            )
            item = _candidate(
                f"station:{station_id}:control_loop",
                "control_loop",
                "error",
                "Regelkreis ausgefallen",
                detail,
                station=station_id,
                station_name=station_name,
            )
            candidates[item["key"]] = item

        sensor_specs = (
            ("temperature", "Temperatursensor"),
            ("humidity", "Feuchtesensor"),
        )
        for sensor_key, label in sensor_specs:
            sensor = station.get(sensor_key) or {}
            if not sensor.get("configured") or not sensor.get("stale"):
                continue

            age = sensor.get("age")
            detail = (
                "Es liegen keine frischen Sensordaten vor."
                if age is None
                else f"Seit {int(float(age))} Sekunden keine frischen Sensordaten."
            )
            item = _candidate(
                f"station:{station_id}:sensor:{sensor_key}:stale",
                "sensor_stale",
                "error",
                f"{label} ohne Daten",
                detail,
                station=station_id,
                station_name=station_name,
            )
            candidates[item["key"]] = item

        limits = _station_limits(station_id)
        temp = station.get("temperature") or {}
        temp_value = _number(temp.get("value"))
        if temp.get("configured") and not temp.get("stale") and temp_value is not None:
            min_temp = limits.get("min_temp")
            max_temp = limits.get("max_temp")

            if min_temp is not None and temp_value < min_temp:
                item = _candidate(
                    f"station:{station_id}:sensor:temperature:limit",
                    "sensor_limits",
                    "critical",
                    "Temperatur kritisch niedrig",
                    f"{temp_value:.1f} °C liegt unter MIN_TEMP {min_temp:.1f} °C.",
                    station=station_id,
                    station_name=station_name,
                )
                candidates[item["key"]] = item
            elif max_temp is not None and temp_value > max_temp:
                item = _candidate(
                    f"station:{station_id}:sensor:temperature:limit",
                    "sensor_limits",
                    "critical",
                    "Temperatur kritisch hoch",
                    f"{temp_value:.1f} °C liegt über MAX_TEMP {max_temp:.1f} °C.",
                    station=station_id,
                    station_name=station_name,
                )
                candidates[item["key"]] = item

        hum = station.get("humidity") or {}
        hum_value = _number(hum.get("value"))
        if hum.get("configured") and not hum.get("stale") and hum_value is not None:
            min_hum = limits.get("min_hum")
            max_hum = limits.get("max_hum")

            if min_hum is not None and hum_value < min_hum:
                item = _candidate(
                    f"station:{station_id}:sensor:humidity:limit",
                    "sensor_limits",
                    "critical",
                    "Luftfeuchte kritisch niedrig",
                    f"{hum_value:.1f} % liegt unter MIN_HUM {min_hum:.1f} %.",
                    station=station_id,
                    station_name=station_name,
                )
                candidates[item["key"]] = item
            elif max_hum is not None and hum_value > max_hum:
                item = _candidate(
                    f"station:{station_id}:sensor:humidity:limit",
                    "sensor_limits",
                    "critical",
                    "Luftfeuchte kritisch hoch",
                    f"{hum_value:.1f} % liegt über MAX_HUM {max_hum:.1f} %.",
                    station=station_id,
                    station_name=station_name,
                )
                candidates[item["key"]] = item

        config = station.get("config") or {}
        if not config.get("ok", True):
            issues = [str(x) for x in (config.get("issues") or [])]
            item = _candidate(
                f"station:{station_id}:configuration",
                "configuration",
                "error",
                "Konfiguration fehlerhaft",
                "; ".join(issues[:5]) or "Stationskonfiguration ist ungültig.",
                station=station_id,
                station_name=station_name,
            )
            candidates[item["key"]] = item

        for endpoint in (station.get("hardware") or {}).get("endpoints") or []:
            if endpoint.get("state") != "error":
                continue

            failures = int(endpoint.get("consecutive_failures") or 0)
            if failures < HARDWARE_FAILURE_THRESHOLD:
                continue

            device = str(endpoint.get("device") or "device")
            label = str(endpoint.get("label") or device)
            host = str(endpoint.get("ip") or "?")
            relay = endpoint.get("relay")
            error = str(endpoint.get("last_error") or "nicht erreichbar")

            item = _candidate(
                f"station:{station_id}:hardware:{device}:{host}:{relay}",
                "hardware",
                "error",
                f"Aktor nicht erreichbar: {label}",
                f"{host} / Relay {relay} · {failures} Fehler in Folge · {error}",
                station=station_id,
                station_name=station_name,
            )
            candidates[item["key"]] = item

        safety = station.get("safety") or {}
        if safety.get("stale"):
            item = _candidate(
                f"station:{station_id}:safety:supervisor",
                "safety",
                "critical",
                "Safety-Supervisor ohne Heartbeat",
                str(safety.get("reason") or "Safety-Status ist nicht frisch."),
                station=station_id,
                station_name=station_name,
            )
            candidates[item["key"]] = item
        elif safety.get("active"):
            blocked = ", ".join(
                str(x) for x in (safety.get("blocked_devices") or [])
            )
            detail = str(
                safety.get("reason") or "Stationsbezogener Failsafe ist aktiv."
            )
            if blocked:
                detail += f" · Blockiert: {blocked}"

            item = _candidate(
                f"station:{station_id}:safety:failsafe",
                "safety",
                "critical",
                "Safety-Failsafe aktiv",
                detail,
                station=station_id,
                station_name=station_name,
            )
            candidates[item["key"]] = item

    controller = snapshot.get("controller") or {}

    for thread_key, thread in (controller.get("threads") or {}).items():
        if thread.get("alive"):
            continue

        label = str(thread.get("label") or thread_key)
        item = _candidate(
            f"controller:thread:{thread_key}",
            "controller",
            "error",
            f"Growstar-Thread ausgefallen: {label}",
            "Der zentrale Hintergrunddienst wird nicht mehr als laufend erkannt.",
        )
        candidates[item["key"]] = item

    mqtt_required = any(
        str((station.get("temperature") or {}).get("source_id") or "").startswith("mqtt:")
        or str((station.get("humidity") or {}).get("source_id") or "").startswith("mqtt:")
        for station in (snapshot.get("stations") or [])
        if station.get("enabled")
    )
    mqtt = controller.get("mqtt") or {}
    if mqtt_required and mqtt.get("stale"):
        age = mqtt.get("age")
        detail = (
            "Noch kein MQTT-Sensortraffic."
            if age is None
            else f"Seit {int(float(age))} Sekunden kein MQTT-Sensortraffic."
        )
        item = _candidate(
            "controller:mqtt:stale",
            "controller",
            "error",
            "MQTT-Sensordaten ausgefallen",
            detail,
        )
        candidates[item["key"]] = item

    return candidates


def _severity_icon(severity):
    return {
        "critical": "🛑",
        "error": "🚨",
        "warning": "⚠️",
    }.get(severity, "⚠️")


def _time_text(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime("%d.%m.%Y %H:%M:%S")


def _duration_text(seconds):
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds} Sek."
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} Min. {sec} Sek."
    hours, minutes = divmod(minutes, 60)
    return f"{hours} Std. {minutes} Min."


def _alarm_message(record, *, kind, now):
    station = record.get("station_name")
    station_line = f"\nStation: {station}" if station else ""

    if kind == "recovery":
        return (
            "✅ Growstar Entwarnung"
            f"{station_line}\n"
            f"{record.get('title')}\n"
            f"Störung behoben nach {_duration_text(now - record.get('first_seen', now))}.\n"
            f"Zeit: {_time_text(now)}"
        )

    if kind == "reminder":
        heading = "🔁 Growstar Alarm weiterhin aktiv"
    else:
        heading = f"{_severity_icon(record.get('severity'))} Growstar Alarm"

    return (
        f"{heading}"
        f"{station_line}\n"
        f"{record.get('title')}\n"
        f"{record.get('detail')}\n"
        f"Zeit: {_time_text(now)}"
    )


def _notifications_available(settings, rule):
    telegram = settings.get("telegram") or {}
    return bool(
        telegram.get("enabled")
        and telegram.get("bot_token")
        and telegram.get("chat_id")
        and (settings.get("rules") or {}).get(rule, False)
    )


def _append_history(event, record, now):
    _HISTORY.append({
        "event": event,
        "timestamp": now,
        "key": record.get("key"),
        "severity": record.get("severity"),
        "rule": record.get("rule"),
        "title": record.get("title"),
        "detail": record.get("detail"),
        "station": record.get("station"),
        "station_name": record.get("station_name"),
    })
    del _HISTORY[:-MAX_HISTORY]


def process_watchdog_snapshot(snapshot, *, now=None):
    global _LAST_CYCLE_AT

    now = time.time() if now is None else float(now)
    _ensure_loaded()

    with _STATE_LOCK:
        _LAST_CYCLE_AT = now

        if _ENGINE_STARTED_AT is not None and now - _ENGINE_STARTED_AT < STARTUP_GRACE_SEC:
            return {
                "startup_grace": True,
                "active_count": len(_ACTIVE),
            }

        settings = load_notification_settings()
        candidates = extract_alarm_candidates(snapshot)
        changed = False

        for key, candidate in candidates.items():
            existing = _ACTIVE.get(key)

            if existing is None:
                record = {
                    **candidate,
                    "first_seen": now,
                    "last_seen": now,
                    "last_notified_at": None,
                }
                _ACTIVE[key] = record
                _append_history("opened", record, now)
                changed = True

                if _notifications_available(settings, record["rule"]):
                    if enqueue_notification(
                        _alarm_message(record, kind="alarm", now=now),
                        event_key=key,
                        kind="alarm",
                    ):
                        record["last_notified_at"] = now
            else:
                existing.update({
                    "severity": candidate["severity"],
                    "title": candidate["title"],
                    "detail": candidate["detail"],
                    "last_seen": now,
                    "station": candidate.get("station"),
                    "station_name": candidate.get("station_name"),
                    "rule": candidate["rule"],
                })

                if _notifications_available(settings, existing["rule"]):
                    last_notified = existing.get("last_notified_at")
                    repeat_minutes = int(settings.get("repeat_minutes") or 0)

                    should_notify = last_notified is None
                    if (
                        not should_notify
                        and repeat_minutes > 0
                        and now - float(last_notified) >= repeat_minutes * 60
                    ):
                        should_notify = True

                    if should_notify:
                        kind = "alarm" if last_notified is None else "reminder"
                        if enqueue_notification(
                            _alarm_message(existing, kind=kind, now=now),
                            event_key=key,
                            kind=kind,
                        ):
                            existing["last_notified_at"] = now
                            changed = True

        recovered_keys = [
            key for key in list(_ACTIVE)
            if key not in candidates
        ]

        for key in recovered_keys:
            record = _ACTIVE.pop(key)
            _append_history("recovered", record, now)
            changed = True

            if (
                settings.get("send_recovery")
                and _notifications_available(settings, record["rule"])
                and record.get("last_notified_at") is not None
            ):
                enqueue_notification(
                    _alarm_message(record, kind="recovery", now=now),
                    event_key=key,
                    kind="recovery",
                )

        if changed:
            _atomic_save()

        return {
            "startup_grace": False,
            "active_count": len(_ACTIVE),
        }


def alarm_runtime_status():
    _ensure_loaded()

    with _STATE_LOCK:
        now = time.time()
        grace_remaining = 0
        if _ENGINE_STARTED_AT is not None:
            grace_remaining = max(
                0,
                int(STARTUP_GRACE_SEC - (now - _ENGINE_STARTED_AT)),
            )

        active = sorted(
            (dict(item) for item in _ACTIVE.values()),
            key=lambda item: (
                {"critical": 0, "error": 1, "warning": 2}.get(
                    item.get("severity"), 9
                ),
                item.get("first_seen", 0),
            ),
        )

        return {
            "thread_alive": any(
                thread.name == "growstar-alerts" and thread.is_alive()
                for thread in threading.enumerate()
            ),
            "started_at": _ENGINE_STARTED_AT,
            "last_cycle_at": _LAST_CYCLE_AT,
            "last_error": _LAST_ERROR,
            "startup_grace_remaining": grace_remaining,
            "active_count": len(active),
            "active": active,
            "history": list(reversed(_HISTORY[-50:])),
        }


def alarm_monitor_loop():
    global _ENGINE_STARTED_AT, _LAST_ERROR

    _ENGINE_STARTED_AT = time.time()

    while True:
        try:
            snapshot = build_watchdog_snapshot()
            process_watchdog_snapshot(snapshot)
            _LAST_ERROR = None
        except Exception as exc:
            _LAST_ERROR = str(exc)

        time.sleep(ALARM_INTERVAL_SEC)
