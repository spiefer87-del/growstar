"""Deterministische Read-only-Erkenntnisse aus der Grow-Intelligence-Timeline."""

from __future__ import annotations

import time

from services.grow_events import analysis_events


ALARM_TYPES = ("alarm_opened", "alarm_recovered")
PROFILE_TYPES = ("day_night_profile_changed", "grow_profile_applied")
PHOTO_TYPES = ("plant_photo_created", "batch_photo_created")
DEVICE_ACTIVITY_TYPES = ("actuator_power_changed",)
OPERATIONAL_CATEGORIES = {"climate", "device", "plant", "media", "alert", "energy"}
CORRELATION_WINDOW_SEC = 15 * 60
SHORT_CYCLE_SECONDS = 3 * 60
SHORT_CYCLE_MIN_COMPLETED = 4

DEVICE_ICONS = {
    "heating": "🔥",
    "fan": "🌬️",
    "vent": "🌀",
    "light": "💡",
    "light2": "💡",
    "irrigation": "💧",
    "humidifier": "💦",
    "dehumidifier": "🫧",
}


def _relative_time(timestamp, now):
    age = max(0, int(now) - int(timestamp))
    if age < 60:
        return "gerade eben"
    if age < 3600:
        return f"vor {age // 60} Min."
    if age < 86400:
        return f"vor {age // 3600} Std."
    days = age // 86400
    return f"vor {days} Tag" if days == 1 else f"vor {days} Tagen"


def _insight(kind, severity, icon, title, summary, *, event=None, evidence=None):
    event = event or {}
    return {
        "kind": kind,
        "severity": severity,
        "icon": icon,
        "title": title,
        "summary": summary,
        "station_id": event.get("station_id"),
        "station_label": event.get("station_label") or "Alle Stationen",
        "occurred_at": event.get("occurred_at"),
        "time_label": event.get("time_label"),
        "evidence_ids": list(evidence or ([event["id"]] if event.get("id") else [])),
    }


def _duration_label(seconds):
    seconds = max(0, int(seconds or 0))
    if seconds < 60:
        return "< 1 Min." if seconds else "0 Min."
    minutes = seconds // 60
    hours, remainder = divmod(minutes, 60)
    if not hours:
        return f"{minutes} Min."
    if not remainder:
        return f"{hours} Std."
    return f"{hours} Std. {remainder} Min."


def _device_label(event, device):
    title = str(event.get("title") or "").strip()
    for suffix in (" eingeschaltet", " ausgeschaltet"):
        if title.endswith(suffix):
            return title[:-len(suffix)]
    return str(device or "Aktor").replace("_", " ").strip().title()


def build_device_activity(*, station_id=None, since=None, station_names=None, now=None):
    """Verdichtet bestätigte Relaiswechsel ohne die Rohereignisse zu verändern."""
    now = int(time.time() if now is None else now)
    station_names = station_names or {}
    rows = analysis_events(
        station_id=station_id,
        include_global=False if station_id else True,
        since=since,
        event_types=DEVICE_ACTIVITY_TYPES,
        limit=5000,
        station_names=station_names,
    )
    groups = {}
    for event in reversed(rows):
        metadata = event.get("metadata") or {}
        device = str(event.get("source_id") or metadata.get("geraet") or "aktor")
        key = (str(event.get("station_id") or ""), device)
        groups.setdefault(key, []).append(event)

    items = []
    for (_, device), events in groups.items():
        open_since = None
        open_event = None
        completed = []
        states = []
        for event in events:
            state = str((event.get("metadata") or {}).get("zustand") or "").upper()
            occurred_at = int(event.get("occurred_at") or 0)
            if state not in {"EIN", "AUS"}:
                continue
            states.append(state)
            if state == "EIN":
                if open_since is None:
                    open_since = occurred_at
                    open_event = event
            elif open_since is not None:
                completed.append(max(0, occurred_at - open_since))
                open_since = None
                open_event = None

        newest = events[-1]
        active = bool(states and states[-1] == "EIN")
        ongoing_seconds = max(0, now - open_since) if active and open_since is not None else 0
        documented_seconds = sum(completed)
        average_seconds = round(sum(completed) / len(completed)) if completed else 0
        short_cycles = sum(1 for duration in completed if duration <= SHORT_CYCLE_SECONDS)
        short_cycle_warning = (
            len(completed) >= SHORT_CYCLE_MIN_COMPLETED
            and short_cycles >= 3
            and short_cycles / len(completed) >= 0.6
        )
        latest_metadata = newest.get("metadata") or {}
        reason = str(latest_metadata.get("grund") or "").strip()
        items.append({
            "station_id": newest.get("station_id"),
            "station_label": newest.get("station_label") or "Alle Stationen",
            "device": device,
            "label": _device_label(newest, device),
            "icon": DEVICE_ICONS.get(device, "⚙️"),
            "transitions": len(states),
            "cycles": len(completed),
            "documented_seconds": documented_seconds,
            "documented_label": _duration_label(documented_seconds),
            "ongoing_seconds": ongoing_seconds,
            "ongoing_label": _duration_label(ongoing_seconds) if active else None,
            "active_since_time_label": open_event.get("time_label") if open_event else None,
            "average_seconds": average_seconds,
            "average_label": _duration_label(average_seconds) if completed else "–",
            "short_cycles": short_cycles,
            "short_cycle_warning": short_cycle_warning,
            "active": active,
            "state_label": "AKTIV" if active else "AUS",
            "latest_at": int(newest.get("occurred_at") or 0),
            "latest_time_label": newest.get("time_label"),
            "latest_reason": reason or None,
            "evidence_ids": [event["id"] for event in reversed(events[-8:])],
        })

    items.sort(
        key=lambda item: (
            not item["short_cycle_warning"],
            -int(item["latest_at"]),
            item["station_label"],
            item["label"],
        )
    )
    return {
        "items": items[:12],
        "devices_total": len(items),
        "transitions_total": sum(item["transitions"] for item in items),
        "cycles_total": sum(item["cycles"] for item in items),
        "documented_seconds_total": sum(item["documented_seconds"] for item in items),
        "documented_label": _duration_label(
            sum(item["documented_seconds"] for item in items)
        ),
        "short_cycle_count": sum(1 for item in items if item["short_cycle_warning"]),
        "source_limited": len(rows) >= 5000,
        "truncated": len(items) > 12,
    }


def _open_alarm_insights(station_id, station_names):
    rows = analysis_events(
        station_id=station_id,
        include_global=True,
        event_types=ALARM_TYPES,
        limit=5000,
        station_names=station_names,
    )
    latest_by_correlation = {}
    for event in rows:
        correlation_id = event.get("correlation_id")
        if correlation_id and correlation_id not in latest_by_correlation:
            latest_by_correlation[correlation_id] = event
    open_events = [
        event for event in latest_by_correlation.values()
        if event.get("event_type") == "alarm_opened"
    ]
    open_events.sort(
        key=lambda event: (int(event.get("occurred_at") or 0), int(event.get("id") or 0)),
        reverse=True,
    )
    return [
        _insight(
            "open_alarm",
            event.get("severity") if event.get("severity") in {"warning", "critical"} else "warning",
            "🚨",
            f"Noch offen: {event.get('title')}",
            "Für diesen Watchdog-Vorgang wurde bisher keine Entwarnung erfasst.",
            event=event,
        )
        for event in open_events[:4]
    ], len(open_events)


def _correlation_insight(rows):
    opened = [
        event for event in rows
        if event.get("event_type") == "alarm_opened"
        and event.get("category") in {"climate", "device"}
        and event.get("station_id")
    ]
    newest_pair = None
    for index, left in enumerate(opened):
        for right in opened[index + 1:]:
            if left.get("station_id") != right.get("station_id"):
                continue
            if left.get("category") == right.get("category"):
                continue
            distance = abs(int(left["occurred_at"]) - int(right["occurred_at"]))
            if distance > CORRELATION_WINDOW_SEC:
                continue
            pair_time = max(int(left["occurred_at"]), int(right["occurred_at"]))
            if newest_pair is None or pair_time > newest_pair[0]:
                newest_pair = (pair_time, left, right, distance)
    if newest_pair is None:
        return None
    _, left, right, distance = newest_pair
    newest = left if int(left["occurred_at"]) >= int(right["occurred_at"]) else right
    return _insight(
        "temporal_correlation",
        "warning",
        "🔗",
        "Klima- und Geräteereignis zeitnah erkannt",
        (
            f"Beide Meldungen traten innerhalb von {max(1, distance // 60)} Minuten auf. "
            "Das ist ein zeitlicher Zusammenhang, keine bestätigte Ursache."
        ),
        event=newest,
        evidence=[left["id"], right["id"]],
    )


def build_insights(
    *, station_id=None, since=None, station_names=None, now=None,
    device_activity=None
):
    """Erzeugt nachvollziehbare Hinweise, ohne Regelwerte zu verändern."""
    now = int(time.time() if now is None else now)
    station_names = station_names or {}
    rows = analysis_events(
        station_id=station_id,
        include_global=True,
        since=since,
        limit=5000,
        station_names=station_names,
    )
    insights, open_count = _open_alarm_insights(station_id, station_names)

    correlation = _correlation_insight(rows)
    if correlation:
        insights.append(correlation)

    device_activity = device_activity or build_device_activity(
        station_id=station_id,
        since=since,
        station_names=station_names,
        now=now,
    )
    for item in (
        entry for entry in device_activity["items"]
        if entry["short_cycle_warning"]
    ):
        event = {
            "station_id": item["station_id"],
            "station_label": item["station_label"],
            "occurred_at": item["latest_at"],
            "time_label": item["latest_time_label"],
        }
        insights.append(_insight(
            "short_cycle",
            "warning",
            item["icon"],
            f"Kurze {item['label']}-Zyklen erkannt",
            (
                f"{item['short_cycles']} von {item['cycles']} vollständig beobachteten "
                "Einschaltphasen dauerten höchstens drei Minuten. Bitte Regel-Toleranz "
                "und Sensorposition prüfen; dies ist keine bestätigte Störung."
            ),
            event=event,
            evidence=item["evidence_ids"],
        ))

    recovered = [event for event in rows if event.get("event_type") == "alarm_recovered"]
    if recovered:
        latest = recovered[0]
        count = len(recovered)
        insights.append(_insight(
            "recoveries",
            "success",
            "✅",
            f"{count} {'Vorgang' if count == 1 else 'Vorgänge'} wieder normal",
            (
                "Im ausgewählten Zeitraum wurde eine Watchdog-Entwarnung erfasst."
                if count == 1
                else f"Im ausgewählten Zeitraum wurden {count} Watchdog-Entwarnungen erfasst."
            ),
            event=latest,
            evidence=[event["id"] for event in recovered[:4]],
        ))

    profile_rows = analysis_events(
        station_id=station_id,
        include_global=False if station_id else True,
        event_types=PROFILE_TYPES,
        limit=100,
        station_names=station_names,
    )
    latest_profiles = {}
    for event in profile_rows:
        key = event.get("station_id") or "global"
        if key not in latest_profiles:
            latest_profiles[key] = event
    for event in list(latest_profiles.values())[:4]:
        insights.append(_insight(
            "profile",
            "info",
            "🌓",
            f"Letztes Profilereignis: {event.get('title')}",
            f"Von Growstar {_relative_time(event['occurred_at'], now)} protokolliert.",
            event=event,
        ))

    photo_rows = analysis_events(
        station_id=station_id,
        include_global=True,
        event_types=PHOTO_TYPES,
        limit=1,
        station_names=station_names,
    )
    if photo_rows:
        latest_photo = photo_rows[0]
        age_days = max(0, now - int(latest_photo["occurred_at"])) // 86400
        if age_days >= 7:
            insights.append(_insight(
                "photo_age",
                "warning",
                "📷",
                "Fotodokumentation liegt länger zurück",
                f"Das letzte Pflanzen- oder Durchgangsfoto wurde {_relative_time(latest_photo['occurred_at'], now)} gespeichert.",
                event=latest_photo,
            ))

    operational_count = sum(
        1 for event in rows if event.get("category") in OPERATIONAL_CATEGORIES
    )
    if not insights:
        insights.append(_insight(
            "collecting",
            "info",
            "🧠",
            "Grow Intelligence sammelt Betriebsdaten",
            "Sobald relevante Zustandswechsel auftreten, erscheinen hier nachvollziehbare Erkenntnisse.",
        ))

    analysis_attention_count = sum(
        1 for item in insights if item["severity"] in {"warning", "critical"}
    )
    if open_count:
        state = "attention"
        headline = f"{open_count} offene {'Meldung' if open_count == 1 else 'Meldungen'}"
    elif analysis_attention_count:
        state = "attention"
        headline = (
            "1 Auffälligkeit erkannt"
            if analysis_attention_count == 1
            else f"{analysis_attention_count} Auffälligkeiten erkannt"
        )
    elif operational_count:
        state = "stable"
        headline = "Keine offenen Watchdog-Vorgänge"
    else:
        state = "collecting"
        headline = "Datenbasis wird aufgebaut"

    severity_order = {"critical": 0, "warning": 1, "success": 2, "info": 3}
    insights.sort(key=lambda item: severity_order.get(item["severity"], 9))
    return {
        "state": state,
        "headline": headline,
        "items": insights[:8],
        "open_count": open_count,
        "attention_count": analysis_attention_count,
        "operational_count": operational_count,
        "evaluated_events": len(rows),
    }


__all__ = (
    "CORRELATION_WINDOW_SEC", "SHORT_CYCLE_MIN_COMPLETED", "SHORT_CYCLE_SECONDS",
    "build_device_activity", "build_insights",
)
