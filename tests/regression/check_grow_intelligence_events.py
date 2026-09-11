#!/usr/bin/env python3
"""Regression für den lokalen Grow-Intelligence-Ereignisspeicher."""

import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from auth.policy import permission_requirement
from services import grow_events


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    original_db = grow_events.DB_FILE
    with tempfile.TemporaryDirectory(prefix="growstar-events-") as temp_dir:
        grow_events.DB_FILE = Path(temp_dir) / "events.db"
        try:
            grow_events.init_grow_event_db()
            grow_events.init_grow_event_db()

            connection = sqlite3.connect(grow_events.DB_FILE)
            try:
                initial_count = connection.execute(
                    "SELECT COUNT(*) FROM grow_events WHERE dedupe_key = ?",
                    ("grow-intelligence:3.17.0:enabled",),
                ).fetchone()[0]
                indexes = {
                    row[1]
                    for row in connection.execute("PRAGMA index_list(grow_events)")
                }
            finally:
                connection.close()

            require(initial_count == 1, "3.17-Aktivierung wird idempotent protokolliert")
            require(
                {
                    "idx_grow_events_station_time",
                    "idx_grow_events_category_time",
                    "idx_grow_events_severity_time",
                    "idx_grow_events_correlation",
                }.issubset(indexes),
                "Ereignis-Timeline besitzt alle benötigten SQLite-Indizes",
            )

            first_id = grow_events.record_event(
                station_id="tent_1",
                occurred_at=200,
                category="climate",
                event_type="temperature_high",
                severity="warning",
                title="Temperatur erhöht",
                summary="Der Messwert liegt oberhalb des Zielkorridors.",
                source="climate_monitor",
                source_id="sensor_1",
                correlation_id="climate:tent_1:200",
                dedupe_key="test:temperature:tent_1:200",
                metadata={"temperature": 29.4, "unit": "°C"},
            )
            duplicate_id = grow_events.record_event(
                station_id="tent_1",
                occurred_at=201,
                category="climate",
                event_type="temperature_high",
                severity="warning",
                title="Darf nicht doppelt erscheinen",
                source="climate_monitor",
                dedupe_key="test:temperature:tent_1:200",
            )
            grow_events.record_event(
                station_id="tent_2",
                occurred_at=300,
                category="device",
                event_type="device_online",
                severity="success",
                title="Gerät online",
                source="watchdog",
            )
            global_id = grow_events.record_event(
                occurred_at=250,
                category="system",
                event_type="maintenance",
                title="Wartungshinweis",
                source="growstar",
            )

            require(first_id == duplicate_id, "Dedupe-Key verhindert doppelte Ereignisse")
            tent_one = grow_events.list_events(
                station_id="tent_1",
                since=100,
                station_names={"tent_1": "Zelt 1"},
            )
            require(
                [item["id"] for item in tent_one["items"]][-2:] == [global_id, first_id]
                and all(item.get("station_id") != "tent_2" for item in tent_one["items"]),
                "Stationsfilter zeigt eigene und globale Ereignisse chronologisch",
            )
            require(
                tent_one["items"][-1]["station_label"] == "Zelt 1"
                and tent_one["items"][-1]["metadata"]["temperature"] == 29.4,
                "Stationsname und strukturierte Metadaten werden aufbereitet",
            )
            warnings = grow_events.list_events(
                category="climate", severity="warning", since=100
            )
            require(
                warnings["total"] == 1 and warnings["items"][0]["id"] == first_id,
                "Kategorie-, Prioritäts- und Zeitraumfilter greifen gemeinsam",
            )
            summary = grow_events.event_summary(station_id="tent_1", since=100)
            require(
                summary["total"] == 3
                and summary["severities"]["warning"] == 1
                and summary["categories"]["system"] == 2,
                "Kennzahlen verwenden denselben Stations- und Zeitraumfilter",
            )

            for field, value in (("category", "unknown"), ("severity", "panic")):
                kwargs = {
                    "category": "system",
                    "event_type": "invalid",
                    "severity": "info",
                    "title": "Ungültig",
                    "source": "test",
                }
                kwargs[field] = value
                try:
                    grow_events.record_event(**kwargs)
                except ValueError:
                    pass
                else:
                    raise AssertionError(f"Ungültiges Feld {field} wurde akzeptiert")
            print("✅ Kategorien und Prioritäten werden streng validiert")
        finally:
            grow_events.DB_FILE = original_db

    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    route_source = (ROOT / "routes/events.py").read_text(encoding="utf-8")
    template = (ROOT / "templates/grow_events.html").read_text(encoding="utf-8")
    require(
        "init_grow_event_db()" in app_source
        and "register_event_routes(app)" in app_source,
        "Ereignisspeicher und Route werden beim App-Start registriert",
    )
    require(
        '@app.get("/grow-control/events")' in route_source
        and "list_events(" in route_source
        and "event_summary(" in route_source,
        "Grow-Intelligence-Seite bleibt eine reine GET-Auswertung",
    )
    require(
        "READ-ONLY · KEINE REGELÄNDERUNG" in template
        and "data-event-filter" in template
        and "Ereignis-Timeline" in template,
        "Timeline kennzeichnet den schreibgeschützten Start der 3.17-Reihe",
    )
    require(
        permission_requirement("/grow-control/events", "GET").permissions
        == ("grow.view",),
        "Grow Intelligence verwendet das bestehende Grow-Anzeigerecht",
    )

    print("✅ Grow Intelligence Ereignisspeicher vollständig geprüft")


if __name__ == "__main__":
    main()
