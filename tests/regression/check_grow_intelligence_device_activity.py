#!/usr/bin/env python3
"""Regression für verdichtete Gerätezyklen in Grow Intelligence."""

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import grow_events
from services.grow_insights import build_device_activity, build_insights


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def add_transition(station_id, device, state, occurred_at, label):
    enabled = state == "EIN"
    return grow_events.record_event(
        station_id=station_id,
        occurred_at=occurred_at,
        category="device",
        event_type="actuator_power_changed",
        severity="info",
        title=f"{label} {'eingeschaltet' if enabled else 'ausgeschaltet'}",
        summary=f"Growstar hat {label} {'eingeschaltet' if enabled else 'ausgeschaltet'}.",
        source="actuator_control",
        source_id=device,
        dedupe_key=f"activity-test:{station_id}:{device}:{state}:{occurred_at}",
        metadata={"geraet": device, "zustand": state, "modus": "ENV", "grund": "Regeltest"},
    )


def main():
    original_db = grow_events.DB_FILE
    now = 1_700_200_000
    with tempfile.TemporaryDirectory(prefix="growstar-device-activity-") as temp_dir:
        grow_events.DB_FILE = Path(temp_dir) / "events.db"
        try:
            grow_events.init_grow_event_db()
            start = now - 2_000
            heating_ids = []
            for offset in (0, 300, 600, 900):
                heating_ids.append(add_transition("tent_1", "heating", "EIN", start + offset, "Heizung"))
                heating_ids.append(add_transition("tent_1", "heating", "AUS", start + offset + 120, "Heizung"))
            fan_id = add_transition("tent_1", "vent", "EIN", now - 500, "Ventilator")
            add_transition("tent_2", "light", "EIN", now - 400, "Beleuchtung")
            add_transition("tent_2", "light", "AUS", now - 100, "Beleuchtung")

            before_total = grow_events.list_events(since=0, limit=250)["total"]
            result = build_device_activity(
                station_id="tent_1",
                since=now - 3_600,
                station_names={"tent_1": "Zelt 1", "tent_2": "Zelt 2"},
                now=now,
            )
            after_total = grow_events.list_events(since=0, limit=250)["total"]
            heating = next(item for item in result["items"] if item["device"] == "heating")
            fan = next(item for item in result["items"] if item["device"] == "vent")

            require(
                result["devices_total"] == 2
                and result["transitions_total"] == 9
                and result["cycles_total"] == 4,
                "Schaltungen werden stationsbezogen je Aktor verdichtet",
            )
            require(
                heating["cycles"] == 4
                and heating["documented_seconds"] == 480
                and heating["average_seconds"] == 120,
                "Vollständige EIN/AUS-Paare liefern belegte Laufzeit und Durchschnitt",
            )
            require(
                heating["short_cycle_warning"] is True
                and heating["short_cycles"] == 4
                and result["short_cycle_count"] == 1,
                "Wiederholte kurze Heizphasen werden vorsichtig als Taktungshinweis markiert",
            )
            require(
                fan["active"] is True
                and fan["documented_seconds"] == 0
                and fan["ongoing_seconds"] == 500
                and fan["average_label"] == "–"
                and fan_id in fan["evidence_ids"],
                "Eine aktive Phase wird separat gezeigt und nicht als belegter Vollzyklus gezählt",
            )
            require(
                all(item["station_id"] == "tent_1" for item in result["items"])
                and all(item["station_label"] == "Zelt 1" for item in result["items"]),
                "Geräteverdichtung vermischt keine Stationen",
            )
            require(
                result["items"][0]["device"] == "heating"
                and set(heating["evidence_ids"]) == set(heating_ids),
                "Auffällige Aktoren stehen zuerst und behalten ihre Ereignisbelege",
            )
            require(
                before_total == after_total,
                "Read-only-Verdichtung verändert oder löscht keine Rohereignisse",
            )
            insights = build_insights(
                station_id="tent_1",
                since=now - 3_600,
                station_names={"tent_1": "Zelt 1", "tent_2": "Zelt 2"},
                now=now,
                device_activity=result,
            )
            short_cycle = next(
                item for item in insights["items"] if item["kind"] == "short_cycle"
            )
            require(
                insights["state"] == "attention"
                and insights["attention_count"] == 1
                and short_cycle["station_id"] == "tent_1"
                and set(short_cycle["evidence_ids"]) == set(heating_ids),
                "Wiederholte Kurztaktung erscheint als belegte aktuelle Erkenntnis",
            )
        finally:
            grow_events.DB_FILE = original_db

    route_source = (ROOT / "routes/events.py").read_text(encoding="utf-8")
    template = (ROOT / "templates/grow_events.html").read_text(encoding="utf-8")
    require(
        "build_device_activity(" in route_source
        and "show_device_activity" in route_source,
        "Route bindet die Verdichtung an Stations-, Zeitraum- und Ereignisfilter",
    )
    require(
        "Verdichtete Geräteaktivität" in template
        and "TAKTUNG PRÜFEN" in template
        and "Vollständiges Ereignisprotokoll" in template
        and '<details class="gi-timeline"' in template,
        "Oberfläche zeigt die Zusammenfassung vor dem geschlossenen Rohprotokoll",
    )
    require(
        "keine bestätigte Störung" in template
        and "Eine noch aktive Phase wird separat angezeigt" in template
        and "Bereits vor dem Zeitraum laufende Phasen werden nicht geschätzt" in template,
        "Oberfläche erklärt Grenzen und behauptet keine automatische Diagnose",
    )

    print("✅ INTELLIGENCE.DEVICE-ACTIVITY.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
