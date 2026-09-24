"""Deterministische Read-only-Erkenntnisse aus der Grow-Intelligence-Timeline."""

from __future__ import annotations

import time

from services.grow_events import analysis_events


ALARM_TYPES = ("alarm_opened", "alarm_recovered")
HEATING_TARGET_TYPES = ("heating_target_missed", "heating_target_recovered")
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


def _decimal_label(value, digits=1):
    try:
        return f"{float(value):.{digits}f}".replace(".", ",")
    except (TypeError, ValueError):
        return None


def _climate_context_label(metadata):
    metadata = metadata if isinstance(metadata, dict) else {}
    parts = []
    profile = str(metadata.get("profil") or "").upper()
    if profile in {"TAG", "NACHT"}:
        parts.append("Tagprofil" if profile == "TAG" else "Nachtprofil")
    temperature = _decimal_label(metadata.get("temperatur_c"))
    humidity = _decimal_label(metadata.get("luftfeuchte_pct"))
    vpd = _decimal_label(metadata.get("vpd_kpa"), 2)
    if temperature:
        parts.append(f"{temperature} °C")
    if humidity:
        parts.append(f"{humidity} %")
    if vpd:
        parts.append(f"VPD {vpd} kPa")
    temp_target = _decimal_label(metadata.get("temperatur_soll_c"))
    temp_tol = _decimal_label(metadata.get("temperatur_toleranz_c"))
    if temp_target:
        parts.append(
            f"Temp.-Soll {temp_target}"
            + (f" ± {temp_tol} °C" if temp_tol else " °C")
        )
    hum_target = _decimal_label(metadata.get("feuchte_soll_pct"))
    hum_tol = _decimal_label(metadata.get("feuchte_toleranz_pct"))
    if hum_target:
        parts.append(
            f"Feuchte-Soll {hum_target}"
            + (f" ± {hum_tol} %" if hum_tol else " %")
        )
    return " · ".join(parts) or None


def _operation_label(mode, strategy):
    labels = {
        "DAUERBETRIEB": "Dauerbetrieb",
        "INTERVALL_DAUERSTROM": "Intervall · Shelly bleibt EIN",
        "INTERVALL_SCHALTEND": "Intervall · Shelly schaltet",
        "INTERVALL_AUS": "Intervall · Shelly bleibt AUS",
        "INTERVALL_UNBEKANNT": "Intervallbetrieb",
        "ZEITPLAN": "Zeitplan",
        "ZEITSCHALTUHR": "Zeitschaltuhr",
        "BEDARFSGESTEUERT": "Umgebungsregelung",
    }
    return labels.get(strategy) or {
        "ON": "Dauerbetrieb",
        "INTERVAL": "Intervallbetrieb",
        "TIME": "Zeitplan",
        "TIMER": "Zeitschaltuhr",
        "ENV": "Umgebungsregelung",
        "OFF": "Aus",
    }.get(mode, mode or "Unbekannter Modus")


def _cycle_delta(start_metadata, end_metadata, key, unit):
    try:
        start = float(start_metadata[key])
        end = float(end_metadata[key])
    except (KeyError, TypeError, ValueError):
        return None
    if not all(-1000 < value < 1000 for value in (start, end)):
        return None
    change = round(end - start, 1)
    return f"{change:+.1f} {unit}".replace(".", ",")


def _pair_device_events(events):
    """Pair ordered transitions once for both overview and verifiable cycle pages."""
    open_event = None
    previous_session = None
    states = []
    cycles = []
    interrupted = duplicate_on = unmatched_off = 0
    for event in events:
        metadata = event.get("metadata") or {}
        state = str(metadata.get("zustand") or "").upper()
        if state not in {"EIN", "AUS"}:
            continue
        session = str(metadata.get("sitzung") or "").strip() or None
        if previous_session and session and session != previous_session and open_event is not None:
            interrupted += 1
            open_event = None
        if session:
            previous_session = session
        states.append(state)
        if state == "EIN":
            if open_event is not None:
                duplicate_on += 1
            open_event = event
        elif open_event is not None:
            started = open_event
            start_meta = started.get("metadata") or {}
            start_session = str(start_meta.get("sitzung") or "").strip()
            start_mode = str(start_meta.get("modus") or "").upper()
            end_mode = str(metadata.get("modus") or "").upper()
            seconds = max(0, int(event.get("occurred_at") or 0) - int(started.get("occurred_at") or 0))
            reliable = bool(start_session and session and start_session == session)
            eligible = reliable and start_mode == end_mode == "ENV"
            cycles.append({
                "start_id": started["id"], "end_id": event["id"],
                "started_at": int(started.get("occurred_at") or 0),
                "ended_at": int(event.get("occurred_at") or 0),
                "start_label": f"{started.get('day_label', '')} {started.get('time_label', '')}".strip(),
                "end_label": f"{event.get('day_label', '')} {event.get('time_label', '')}".strip(),
                "seconds": seconds, "duration_label": _duration_label(seconds),
                "short": seconds <= SHORT_CYCLE_SECONDS,
                "warning_eligible": eligible,
                "quality_note": None if reliable and start_mode == end_mode and start_mode else (
                    "Regelart wechselte oder fehlt" if reliable else
                    "Sitzungskennung fehlt; Neustart dazwischen nicht ausschließbar"
                ),
                "mode_label": _operation_label(start_mode, str(start_meta.get("relaisstrategie") or "").upper()),
                "temperature_delta": _cycle_delta(start_meta, metadata, "temperatur_c", "°C"),
                "humidity_delta": _cycle_delta(start_meta, metadata, "luftfeuchte_pct", "%"),
            })
            open_event = None
        else:
            unmatched_off += 1
    return {
        "cycles": cycles, "states": states, "open_event": open_event,
        "restart_interruptions": interrupted,
        "duplicate_on": duplicate_on, "unmatched_off": unmatched_off,
    }


def build_device_cycle_log(*, station_id, device, since=None, station_names=None, page=1, per_page=25):
    """Read-only, paginated evidence for every matched cycle in the selected window."""
    rows = analysis_events(
        station_id=station_id, include_global=False, since=since,
        event_types=DEVICE_ACTIVITY_TYPES, limit=5000, station_names=station_names,
    )
    events = [row for row in reversed(rows) if str(row.get("source_id") or (row.get("metadata") or {}).get("geraet") or "aktor") == device]
    paired = _pair_device_events(events)
    cycles = list(reversed(paired["cycles"]))
    per_page = max(1, min(50, int(per_page)))
    pages = max(1, (len(cycles) + per_page - 1) // per_page)
    page = max(1, min(int(page), pages))
    return {
        "items": cycles[(page - 1) * per_page:page * per_page],
        "total": len(cycles), "page": page, "pages": pages,
        "source_limited": len(rows) >= 5000,
        "restart_interruptions": paired["restart_interruptions"],
        "unmatched_off": paired["unmatched_off"],
        "duplicate_on": paired["duplicate_on"],
        "open_event": paired["open_event"],
    }


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
        paired = _pair_device_events(events)
        completed_cycles = paired["cycles"]
        completed = [cycle["seconds"] for cycle in completed_cycles]
        eligible_cycles = [cycle for cycle in completed_cycles if cycle["warning_eligible"]]
        states = paired["states"]
        open_event = paired["open_event"]
        restart_interruptions = paired["restart_interruptions"]
        duplicate_on = paired["duplicate_on"]
        unmatched_off = paired["unmatched_off"]

        newest = events[-1]
        latest_metadata = newest.get("metadata") or {}
        mode = str(latest_metadata.get("modus") or "").upper()
        strategy = str(latest_metadata.get("relaisstrategie") or "").upper()
        continuous_operation = (
            mode == "ON"
            or strategy in {"DAUERBETRIEB", "INTERVALL_DAUERSTROM"}
        )
        active = bool(states and states[-1] == "EIN")
        ongoing_seconds = max(0, now - int(open_event.get("occurred_at") or 0)) if active and open_event is not None else 0
        documented_seconds = sum(completed)
        average_seconds = round(sum(completed) / len(completed)) if completed else 0
        short_cycles = sum(1 for cycle in eligible_cycles if cycle["short"])
        short_cycle_warning = (
            mode == "ENV"
            and len(eligible_cycles) >= SHORT_CYCLE_MIN_COMPLETED
            and short_cycles >= 3
            and short_cycles / len(eligible_cycles) >= 0.6
        )
        if completed:
            average_display = _duration_label(average_seconds)
        elif continuous_operation:
            average_display = "nicht nötig"
        elif mode == "INTERVAL":
            average_display = "kein Relais-Aus"
        elif active:
            average_display = "Phase offen"
        else:
            average_display = "kein Vollzyklus"

        cycle_notes = []
        if strategy == "INTERVALL_DAUERSTROM":
            cycle_notes.append(
                "In beiden Intervallphasen bleibt Shelly-Power EIN; nur die Controllerwerte wechseln."
            )
        elif mode == "ON" or strategy == "DAUERBETRIEB":
            cycle_notes.append("Im Dauerbetrieb ist kein regelmäßiger AUS-Zyklus vorgesehen.")
        elif mode == "INTERVAL" and not completed:
            cycle_notes.append(
                "Im Intervallbetrieb wurde bisher kein Relais-AUS erfasst; abhängig vom Phasenprofil kann das korrekt sein."
            )
        elif active and not completed:
            cycle_notes.append("Der erste Durchschnitt folgt nach einem bestätigten Ausschalten.")
        elif unmatched_off and not completed:
            cycle_notes.append(
                "Der Beginn lag vor dem Zeitraum oder wurde noch nicht protokolliert."
            )
        if restart_interruptions:
            cycle_notes.append(
                f"{restart_interruptions} offene Phase(n) wurden an einem App-Neustart getrennt."
            )
        if duplicate_on:
            cycle_notes.append(
                f"{duplicate_on} erneute EIN-Meldung(en) ohne vorheriges AUS wurden nicht als Vollzyklus gezählt."
            )
        uncertain_cycles = len(completed_cycles) - len(eligible_cycles)
        if mode == "ENV" and uncertain_cycles:
            cycle_notes.append(
                f"{uncertain_cycles} Zyklus/Zyklen gehen nicht in die Kurztakt-Bewertung ein (ältere Daten oder geänderte Regelart)."
            )
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
            "average_display": average_display,
            "short_cycles": short_cycles,
            "warning_eligible_cycles": len(eligible_cycles),
            "cycle_examples": list(reversed(completed_cycles[-3:])),
            "recent_short_cycles": list(reversed([cycle for cycle in eligible_cycles if cycle["short"]][-3:])),
            "short_cycle_evidence_ids": [
                event_id for cycle in reversed([cycle for cycle in eligible_cycles if cycle["short"]][-3:])
                for event_id in (cycle["start_id"], cycle["end_id"])
            ],
            "short_cycle_warning": short_cycle_warning,
            "continuous_operation": continuous_operation,
            "operation_label": _operation_label(mode, strategy),
            "cycle_note": " ".join(cycle_notes) or None,
            "restart_interruptions": restart_interruptions,
            "duplicate_on": duplicate_on,
            "unmatched_off": unmatched_off,
            "climate_context": _climate_context_label(latest_metadata),
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


def _heating_target_insights(station_id, station_names):
    # The newest event for each station represents its current heater episode.
    rows = analysis_events(
        station_id=station_id, include_global=False,
        event_types=HEATING_TARGET_TYPES, limit=100,
        station_names=station_names,
    )
    newest = {}
    for event in rows:
        newest.setdefault(event.get("station_id"), event)
    return [
        _insight(
            "heating_target_missed", "warning", "🔥",
            "Heizung erreicht Solltemperatur nicht",
            event.get("summary") or "Die Solltemperatur wurde nach 30 Minuten Heizen nicht erreicht.",
            event=event,
        )
        for event in newest.values()
        if event.get("event_type") == "heating_target_missed"
    ]


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
    heating_insights = _heating_target_insights(station_id, station_names)
    insights.extend(heating_insights)
    open_count += len(heating_insights)

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
                f"{item['short_cycles']} von {item['warning_eligible_cycles']} vergleichbaren "
                "Einschaltphasen dauerten höchstens drei Minuten. Bitte Regel-Toleranz "
                "und Sensorposition prüfen; dies ist keine bestätigte Störung."
            ),
            event=event,
            evidence=item["short_cycle_evidence_ids"],
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
        headline = "Keine offenen Meldungen"
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
    "build_device_activity", "build_device_cycle_log", "build_insights",
)
