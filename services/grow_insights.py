"""Deterministische Read-only-Erkenntnisse aus der Grow-Intelligence-Timeline."""

from __future__ import annotations

import time

from services.grow_events import analysis_events


ALARM_TYPES = ("alarm_opened", "alarm_recovered")
PROFILE_TYPES = ("day_night_profile_changed", "grow_profile_applied")
PHOTO_TYPES = ("plant_photo_created", "batch_photo_created")
OPERATIONAL_CATEGORIES = {"climate", "device", "plant", "media", "alert", "energy"}
CORRELATION_WINDOW_SEC = 15 * 60


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


def build_insights(*, station_id=None, since=None, station_names=None, now=None):
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

    if open_count:
        state = "attention"
        headline = f"{open_count} offene {'Meldung' if open_count == 1 else 'Meldungen'}"
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
        "operational_count": operational_count,
        "evaluated_events": len(rows),
    }


__all__ = ("CORRELATION_WINDOW_SEC", "build_insights")
