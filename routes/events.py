"""Read-only Webansicht für Grow-Intelligence-Ereignisse."""

import time

from flask import render_template, request

from core.tents import manager as tent_manager
from services.grow_events import (
    CATEGORIES,
    SEVERITIES,
    event_queue_status,
    event_summary,
    list_events,
)
from services.grow_insights import build_insights


RANGES = {
    "24h": {"label": "Letzte 24 Stunden", "seconds": 24 * 60 * 60},
    "7d": {"label": "Letzte 7 Tage", "seconds": 7 * 24 * 60 * 60},
    "30d": {"label": "Letzte 30 Tage", "seconds": 30 * 24 * 60 * 60},
    "all": {"label": "Gesamter Zeitraum", "seconds": None},
}


def _selection(value, allowed, fallback="all"):
    value = str(value or fallback).strip()
    return value if value in allowed else fallback


def register(app):
    @app.get("/grow-control/events")
    def grow_control_events():
        tents = tent_manager.list_tents()
        station_names = {
            str(tent.get("id")): str(tent.get("name") or tent.get("id"))
            for tent in tents
            if tent.get("id")
        }
        requested_station = str(request.args.get("station") or "all").strip()
        station_id = requested_station if requested_station in station_names else None
        selected_station = station_id or "all"
        selected_category = _selection(request.args.get("category"), CATEGORIES)
        selected_severity = _selection(request.args.get("severity"), SEVERITIES)
        selected_range = _selection(request.args.get("range"), RANGES, "7d")
        seconds = RANGES[selected_range]["seconds"]
        since = int(time.time()) - seconds if seconds is not None else None

        try:
            page = max(1, int(request.args.get("page") or 1))
        except (TypeError, ValueError):
            page = 1
        page_size = 60
        result = list_events(
            station_id=station_id,
            category=None if selected_category == "all" else selected_category,
            severity=None if selected_severity == "all" else selected_severity,
            since=since,
            limit=page_size,
            offset=(page - 1) * page_size,
            station_names=station_names,
        )
        last_page = max(1, (result["total"] + page_size - 1) // page_size)
        if page > last_page:
            page = last_page
            result = list_events(
                station_id=station_id,
                category=None if selected_category == "all" else selected_category,
                severity=None if selected_severity == "all" else selected_severity,
                since=since,
                limit=page_size,
                offset=(page - 1) * page_size,
                station_names=station_names,
            )

        return render_template(
            "grow_events.html",
            events=result["items"],
            total=result["total"],
            summary=event_summary(station_id=station_id, since=since),
            tents=tents,
            categories=CATEGORIES,
            severities=SEVERITIES,
            ranges=RANGES,
            selected_station=selected_station,
            selected_category=selected_category,
            selected_severity=selected_severity,
            selected_range=selected_range,
            page=page,
            last_page=last_page,
            queue_status=event_queue_status(),
            insights=build_insights(
                station_id=station_id,
                since=since,
                station_names=station_names,
            ),
        )


__all__ = ("RANGES", "register")
