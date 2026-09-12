"""Lokaler Ereignisspeicher für Grow Intelligence."""

from __future__ import annotations

import json
import queue
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path


DB_FILE = Path(__file__).resolve().parent.parent / "data.db"

CATEGORIES = {
    "climate": {"label": "Klima", "icon": "🌡️"},
    "device": {"label": "Geräte", "icon": "⚙️"},
    "plant": {"label": "Pflanzen", "icon": "🌿"},
    "media": {"label": "Medien", "icon": "📷"},
    "alert": {"label": "Warnungen", "icon": "🔔"},
    "energy": {"label": "Energie", "icon": "⚡"},
    "system": {"label": "System", "icon": "🧠"},
}

SEVERITIES = {
    "info": {"label": "Information"},
    "success": {"label": "Erfolgreich"},
    "warning": {"label": "Hinweis"},
    "critical": {"label": "Kritisch"},
}

EVENT_QUEUE_SIZE = 1000
_EVENT_QUEUE = queue.Queue(maxsize=EVENT_QUEUE_SIZE)
_DROPPED_EVENTS = 0

SETTING_DESCRIPTORS = {
    "DAY_TEMP": ("Tag-Solltemperatur", "°C"),
    "NIGHT_TEMP": ("Nacht-Solltemperatur", "°C"),
    "DAY_HUM": ("Tag-Sollfeuchte", "%"),
    "NIGHT_HUM": ("Nacht-Sollfeuchte", "%"),
    "DAY_TEMP_TOL": ("Tag-Temperaturtoleranz", "°C"),
    "NIGHT_TEMP_TOL": ("Nacht-Temperaturtoleranz", "°C"),
    "DAY_HUM_TOL": ("Tag-Feuchtetoleranz", "%"),
    "NIGHT_HUM_TOL": ("Nacht-Feuchtetoleranz", "%"),
    "MIN_TEMP": ("Absolute Mindesttemperatur", "°C"),
    "MAX_TEMP": ("Absolute Höchsttemperatur", "°C"),
    "MIN_HUM": ("Absolute Mindestfeuchte", "%"),
    "MAX_HUM": ("Absolute Höchstfeuchte", "%"),
    "DAY_START_MIN": ("Tagbeginn", "time"),
    "NIGHT_START_MIN": ("Nachtbeginn", "time"),
    "RAMP_ENABLED": ("Profilrampe", "switch"),
    "RAMP_DURATION_MIN": ("Rampendauer", "Min."),
    "LIGHT_SUN_ENABLED": ("Sonnenverlauf", "switch"),
    "LIGHT_SUNRISE_DURATION_MIN": ("Sonnenaufgang", "Min."),
    "LIGHT_SUNSET_DURATION_MIN": ("Sonnenuntergang", "Min."),
    "LIGHT_SUN_MIN_LEVEL": ("Minimale Lichtstufe", "Stufe"),
    "VPD_TARGET_DAY": ("Tag-VPD-Ziel", "kPa"),
    "VPD_TOLERANCE_DAY": ("Tag-VPD-Toleranz", "kPa"),
    "VPD_TARGET_NIGHT": ("Nacht-VPD-Ziel", "kPa"),
    "VPD_TOLERANCE_NIGHT": ("Nacht-VPD-Toleranz", "kPa"),
    "VPD_TEMP_MIN_DAY": ("Tag-VPD Temperatur Minimum", "°C"),
    "VPD_TEMP_MAX_DAY": ("Tag-VPD Temperatur Maximum", "°C"),
    "VPD_HUM_MIN_DAY": ("Tag-VPD Feuchte Minimum", "%"),
    "VPD_HUM_MAX_DAY": ("Tag-VPD Feuchte Maximum", "%"),
    "VPD_TEMP_MIN_NIGHT": ("Nacht-VPD Temperatur Minimum", "°C"),
    "VPD_TEMP_MAX_NIGHT": ("Nacht-VPD Temperatur Maximum", "°C"),
    "VPD_HUM_MIN_NIGHT": ("Nacht-VPD Feuchte Minimum", "%"),
    "VPD_HUM_MAX_NIGHT": ("Nacht-VPD Feuchte Maximum", "%"),
    "VPD_SECONDARY_PRIORITY_DAY": ("Tag-VPD Priorität 2", "choice"),
    "VPD_SECONDARY_PRIORITY_NIGHT": ("Nacht-VPD Priorität 2", "choice"),
}


def _db():
    connection = sqlite3.connect(DB_FILE, timeout=10, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def _text(value, *, maximum=500):
    return str(value or "").strip()[:maximum]


def _timestamp(value=None):
    if value is None:
        return int(time.time())
    if isinstance(value, datetime):
        return int(value.timestamp())
    return int(value)


def init_grow_event_db():
    """Legt das additive 3.17-Schema sicher und idempotent an."""
    connection = _db()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS grow_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_id TEXT,
                occurred_at INTEGER NOT NULL,
                category TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'info',
                title TEXT NOT NULL,
                summary TEXT,
                source TEXT NOT NULL,
                source_id TEXT,
                correlation_id TEXT,
                dedupe_key TEXT UNIQUE,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_grow_events_station_time
            ON grow_events(station_id, occurred_at DESC, id DESC);
            CREATE INDEX IF NOT EXISTS idx_grow_events_category_time
            ON grow_events(category, occurred_at DESC, id DESC);
            CREATE INDEX IF NOT EXISTS idx_grow_events_severity_time
            ON grow_events(severity, occurred_at DESC, id DESC);
            CREATE INDEX IF NOT EXISTS idx_grow_events_correlation
            ON grow_events(correlation_id);
            """
        )
        connection.commit()
    finally:
        connection.close()

    record_event(
        category="system",
        event_type="grow_intelligence_enabled",
        severity="success",
        title="Grow Intelligence aktiviert",
        summary=(
            "Der zentrale Ereignisspeicher und die stationsbezogene Timeline "
            "wurden eingerichtet. Die Regelung bleibt unverändert."
        ),
        source="growstar",
        source_id="3.17.0",
        dedupe_key="grow-intelligence:3.17.0:enabled",
        metadata={"version": "3.17.0", "mode": "read_only"},
    )


def record_event(
    *, category, event_type, title, source, station_id=None, occurred_at=None,
    severity="info", summary=None, source_id=None, correlation_id=None,
    dedupe_key=None, metadata=None
):
    """Speichert ein normalisiertes Ereignis; Deduplizierung ist optional."""

    category = _text(category, maximum=40).lower()
    severity = _text(severity, maximum=20).lower()
    event_type = _text(event_type, maximum=100).lower()
    title = _text(title, maximum=180)
    source = _text(source, maximum=100).lower()
    if category not in CATEGORIES:
        raise ValueError("Unbekannte Grow-Intelligence-Kategorie")
    if severity not in SEVERITIES:
        raise ValueError("Unbekannte Grow-Intelligence-Priorität")
    if not event_type or not title or not source:
        raise ValueError("Ereignistyp, Titel und Quelle sind erforderlich")

    metadata_json = json.dumps(
        metadata if isinstance(metadata, dict) else {},
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    if len(metadata_json) > 16000:
        raise ValueError("Ereignis-Metadaten sind zu groß")

    now = int(time.time())
    values = (
        _text(station_id, maximum=80) or None,
        _timestamp(occurred_at),
        category,
        event_type,
        severity,
        title,
        _text(summary, maximum=2000) or None,
        source,
        _text(source_id, maximum=180) or None,
        _text(correlation_id, maximum=180) or None,
        _text(dedupe_key, maximum=240) or None,
        metadata_json,
        now,
    )
    connection = _db()
    try:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO grow_events (
                station_id, occurred_at, category, event_type, severity,
                title, summary, source, source_id, correlation_id,
                dedupe_key, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        connection.commit()
        if cursor.lastrowid:
            return int(cursor.lastrowid)
        if values[10]:
            row = connection.execute(
                "SELECT id FROM grow_events WHERE dedupe_key = ?", (values[10],)
            ).fetchone()
            return int(row["id"]) if row else None
        return None
    finally:
        connection.close()


def enqueue_event(**event):
    """Übergibt ein Ereignis ohne Wartezeit an den getrennten DB-Writer."""
    global _DROPPED_EVENTS
    try:
        _EVENT_QUEUE.put_nowait(dict(event))
        return True
    except queue.Full:
        _DROPPED_EVENTS += 1
        if _DROPPED_EVENTS == 1 or _DROPPED_EVENTS % 100 == 0:
            print(f"⚠️ Grow Intelligence Queue voll · {_DROPPED_EVENTS} Ereignis(se) verworfen")
        return False


def _setting_value(key, value, unit):
    if value is None:
        return "—"
    if unit == "time":
        try:
            minutes = max(0, min(1439, int(value)))
            return f"{minutes // 60:02d}:{minutes % 60:02d} Uhr"
        except (TypeError, ValueError):
            return str(value)
    if unit == "switch":
        return "Ein" if bool(value) else "Aus"
    if unit == "choice":
        return {
            "TEMPERATURE": "Temperatur",
            "HUMIDITY": "Feuchtigkeit",
        }.get(str(value).upper(), str(value))
    if isinstance(value, bool):
        text = "Ja" if value else "Nein"
    elif isinstance(value, (int, float)):
        text = f"{float(value):.3f}".rstrip("0").rstrip(".").replace(".", ",")
    else:
        text = str(value)
    return f"{text} {unit}" if unit else text


def describe_setting_changes(changes, *, limit=12):
    """Formatiert ausschließlich freigegebene, nicht geheime Regelwerte."""
    described = []
    for key in sorted(changes or {}):
        descriptor = SETTING_DESCRIPTORS.get(str(key))
        values = changes.get(key)
        if not descriptor or not isinstance(values, dict):
            continue
        before = values.get("before")
        after = values.get("after")
        if before == after:
            continue
        label, unit = descriptor
        before_label = _setting_value(key, before, unit)
        after_label = _setting_value(key, after, unit)
        described.append({
            "key": str(key),
            "label": label,
            "before": before_label,
            "after": after_label,
            "text": f"{label}: {before_label} → {after_label}",
        })
    return described[:max(1, int(limit))]


def enqueue_setting_change_event(
    *, changes, title, source, event_type="settings_updated",
    station_id=None, source_id=None, summary_suffix=None, metadata=None
):
    """Erzeugt genau ein lesbares Ereignis je erfolgreichem Speichervorgang."""
    described = describe_setting_changes(changes)
    if not described:
        return False
    visible = described[:4]
    remaining = len(described) - len(visible)
    summary = "; ".join(item["text"] for item in visible)
    if remaining:
        summary += f"; +{remaining} weitere Änderung(en)"
    summary += "."
    if summary_suffix:
        summary += f" {str(summary_suffix).strip()}"
    event_metadata = dict(metadata or {})
    event_metadata["geändert"] = len(described)
    for index, item in enumerate(described[:8], start=1):
        event_metadata[f"änderung_{index}"] = item["text"]
    occurred_at = int(time.time())
    return enqueue_event(
        station_id=station_id,
        occurred_at=occurred_at,
        category="climate",
        event_type=event_type,
        severity="info",
        title=title,
        summary=summary,
        source=source,
        source_id=source_id,
        dedupe_key=(
            f"setting-change:{source}:{station_id or 'global'}:"
            f"{source_id or '-'}:{time.time_ns()}"
        ),
        metadata=event_metadata,
    )


def _write_event_safely(event):
    try:
        return record_event(**event)
    except Exception as exc:
        # Ereignisprotokollierung darf niemals Regelung, Watchdog oder Medien
        # beeinflussen. Der Fehler bleibt deshalb lokal beim Writer.
        print("⚠️ Grow Intelligence Ereignis konnte nicht gespeichert werden:", exc)
        return None


def flush_event_queue(*, limit=100):
    """Schreibt bereits wartende Ereignisse; auch für deterministische Tests."""
    written = 0
    for _ in range(max(1, int(limit))):
        try:
            event = _EVENT_QUEUE.get_nowait()
        except queue.Empty:
            break
        try:
            _write_event_safely(event)
            written += 1
        finally:
            _EVENT_QUEUE.task_done()
    return written


def grow_event_writer_loop():
    print("🧠 Grow Intelligence Event-Writer gestartet")
    while True:
        event = _EVENT_QUEUE.get()
        try:
            _write_event_safely(event)
        finally:
            _EVENT_QUEUE.task_done()


def event_queue_status():
    return {
        "queued": _EVENT_QUEUE.qsize(),
        "capacity": EVENT_QUEUE_SIZE,
        "dropped": _DROPPED_EVENTS,
        "writer_alive": any(
            thread.name == "growstar-events" and thread.is_alive()
            for thread in threading.enumerate()
        ),
    }


def _where(
    *, station_id=None, include_global=True, category=None, severity=None,
    since=None, include_boot_profile_events=False
):
    clauses = []
    params = []
    if not include_boot_profile_events:
        clauses.append(
            """NOT (
                event_type = 'grow_intelligence_enabled'
                OR (
                    event_type = 'day_night_profile_changed'
                    AND source = 'profile_scheduler'
                    AND (
                        COALESCE(metadata_json, '') LIKE '%\"vorher\":\"unbekannt\"%'
                        OR COALESCE(summary, '') LIKE 'Growstar hat beim Start%'
                    )
                )
            )"""
        )
    if station_id:
        clauses.append("(station_id = ? OR station_id IS NULL)" if include_global else "station_id = ?")
        params.append(str(station_id))
    if category:
        clauses.append("category = ?")
        params.append(str(category))
    if severity:
        clauses.append("severity = ?")
        params.append(str(severity))
    if since is not None:
        clauses.append("occurred_at >= ?")
        params.append(int(since))
    return (" AND ".join(clauses) if clauses else "1 = 1"), params


def _decorate(row, station_names=None):
    item = dict(row)
    try:
        metadata = json.loads(item.get("metadata_json") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        metadata = {}
    item["metadata"] = metadata if isinstance(metadata, dict) else {}
    occurred = datetime.fromtimestamp(int(item["occurred_at"])).astimezone()
    item["date_key"] = occurred.strftime("%Y-%m-%d")
    item["day_label"] = occurred.strftime("%d.%m.%Y")
    item["time_label"] = occurred.strftime("%H:%M:%S")
    item["category_label"] = CATEGORIES[item["category"]]["label"]
    item["category_icon"] = CATEGORIES[item["category"]]["icon"]
    item["severity_label"] = SEVERITIES[item["severity"]]["label"]
    station_names = station_names or {}
    item["station_label"] = (
        station_names.get(item.get("station_id"), item.get("station_id"))
        if item.get("station_id") else "Alle Stationen"
    )
    return item


def list_events(
    *, station_id=None, include_global=True, category=None, severity=None,
    since=None, limit=100, offset=0, station_names=None,
    include_boot_profile_events=False
):
    where, params = _where(
        station_id=station_id, include_global=include_global,
        category=category, severity=severity, since=since,
        include_boot_profile_events=include_boot_profile_events,
    )
    limit = max(1, min(int(limit), 250))
    offset = max(0, int(offset))
    connection = _db()
    try:
        total_row = connection.execute(
            f"SELECT COUNT(*) AS count FROM grow_events WHERE {where}", params
        ).fetchone()
        rows = connection.execute(
            f"""SELECT * FROM grow_events WHERE {where}
            ORDER BY occurred_at DESC, id DESC LIMIT ? OFFSET ?""",
            [*params, limit, offset],
        ).fetchall()
    finally:
        connection.close()
    return {
        "items": [_decorate(row, station_names) for row in rows],
        "total": int(total_row["count"] if total_row else 0),
        "limit": limit,
        "offset": offset,
    }


def analysis_events(
    *, station_id=None, include_global=True, since=None, event_types=None,
    limit=2000, station_names=None, include_boot_profile_events=False
):
    """Liefert eine begrenzte, chronologische Datenbasis für Read-only-Analysen."""
    where, params = _where(
        station_id=station_id,
        include_global=include_global,
        since=since,
        include_boot_profile_events=include_boot_profile_events,
    )
    normalized_types = tuple(
        _text(value, maximum=100).lower()
        for value in (event_types or ())
        if _text(value, maximum=100)
    )
    if normalized_types:
        placeholders = ",".join("?" for _ in normalized_types)
        where += f" AND event_type IN ({placeholders})"
        params.extend(normalized_types)
    limit = max(1, min(int(limit), 5000))
    connection = _db()
    try:
        rows = connection.execute(
            f"""SELECT * FROM grow_events WHERE {where}
            ORDER BY occurred_at DESC, id DESC LIMIT ?""",
            [*params, limit],
        ).fetchall()
    finally:
        connection.close()
    return [_decorate(row, station_names) for row in rows]


def event_summary(
    *, station_id=None, include_global=True, since=None,
    include_boot_profile_events=False
):
    where, params = _where(
        station_id=station_id,
        include_global=include_global,
        since=since,
        include_boot_profile_events=include_boot_profile_events,
    )
    connection = _db()
    try:
        total = connection.execute(
            f"SELECT COUNT(*) AS count FROM grow_events WHERE {where}", params
        ).fetchone()
        severity_rows = connection.execute(
            f"SELECT severity, COUNT(*) AS count FROM grow_events WHERE {where} GROUP BY severity",
            params,
        ).fetchall()
        category_rows = connection.execute(
            f"SELECT category, COUNT(*) AS count FROM grow_events WHERE {where} GROUP BY category",
            params,
        ).fetchall()
    finally:
        connection.close()
    return {
        "total": int(total["count"] if total else 0),
        "severities": {row["severity"]: int(row["count"]) for row in severity_rows},
        "categories": {row["category"]: int(row["count"]) for row in category_rows},
    }


__all__ = (
    "CATEGORIES", "SEVERITIES", "analysis_events", "describe_setting_changes",
    "enqueue_event", "enqueue_setting_change_event", "event_queue_status",
    "event_summary", "flush_event_queue", "grow_event_writer_loop",
    "init_grow_event_db", "list_events", "record_event",
)
