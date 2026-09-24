#!/usr/bin/env python3
"""Evidence-backed heating cycles, quality gates and paginated drill-down."""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from services import grow_events
from services.grow_insights import build_device_activity, build_device_cycle_log


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def add(state, timestamp, *, session="lauf", mode="ENV", temp=None):
    return grow_events.record_event(
        station_id="tent_2", occurred_at=timestamp,
        category="device", event_type="actuator_power_changed",
        title=f"Heizung {'eingeschaltet' if state == 'EIN' else 'ausgeschaltet'}",
        source="actuator_control", source_id="heating",
        metadata={
            "geraet": "heating", "zustand": state, "modus": mode,
            "sitzung": session, "temperatur_c": temp,
        },
    )


def main():
    old_db = grow_events.DB_FILE
    base = 1_700_000_000
    with tempfile.TemporaryDirectory(prefix="growstar-cycle-evidence-") as directory:
        grow_events.DB_FILE = Path(directory) / "events.db"
        try:
            grow_events.init_grow_event_db()
            add("EIN", base, temp=24.8)
            add("AUS", base + 181, temp=25.2)
            add("EIN", base + 400, temp=24.8)
            add("AUS", base + 570, temp=25.1)
            add("EIN", base + 800, temp=24.8)
            add("AUS", base + 960, temp=25.2)
            add("EIN", base + 1200, temp=24.8)
            add("AUS", base + 1380, temp=25.0)
            activity = build_device_activity(station_id="tent_2", since=base-1, now=base+2000)
            heating = activity["items"][0]
            require(heating["cycles"] == 4 and heating["short_cycles"] == 3 and heating["warning_eligible_cycles"] == 4, "3:01 liegt außerhalb der Kurztakt-Grenze; 3:00 zählt noch")
            require(heating["short_cycle_warning"] is True, "Drei kurze von vier belegten ENV-Paaren lösen einen Hinweis aus")
            log = build_device_cycle_log(station_id="tent_2", device="heating", since=base-1, page=1, per_page=2)
            require(log["total"] == 4 and log["pages"] == 2 and len(log["items"]) == 2, "Zyklen werden vollständig und seitenweise bereitgestellt")
            require(log["items"][0]["seconds"] == 180 and log["items"][0]["temperature_delta"] == "+0,2 °C", "Ereignispaar enthält genaue Dauer und zwei Sensorwerte")
            older = build_device_cycle_log(station_id="tent_2", device="heating", since=base-1, page=2, per_page=2)
            require(older["items"][-1]["seconds"] == 181 and older["items"][-1]["short"] is False, "Seite zwei enthält den nachvollziehbaren 3:01-Zyklus")
            add("EIN", base + 2200, session=None)
            add("AUS", base + 2230, session=None)
            add("EIN", base + 2500, mode="ENV")
            add("AUS", base + 2530, mode="TIME")
            add("EIN", base + 2800, session="vor")
            add("AUS", base + 2830, session="nach")
            activity = build_device_activity(station_id="tent_2", since=base-1, now=base+3000)
            heating = activity["items"][0]
            require(heating["cycles"] == 6 and heating["warning_eligible_cycles"] == 4 and heating["short_cycles"] == 3, "Alte und gemischte Paare bleiben sichtbar, verändern die Warnung aber nicht")
            require(heating["restart_interruptions"] == 1 and heating["unmatched_off"] == 1, "Neustart unterbricht ein offenes Paar statt einen falschen 30-Sekunden-Zyklus zu erzeugen")
            require(build_device_cycle_log(station_id="tent_1", device="heating", since=base-1)["total"] == 0, "Andere Stationen bleiben getrennt")
        finally:
            grow_events.DB_FILE = old_db
    template = (ROOT / "templates/grow_events.html").read_text(encoding="utf-8")
    drilldown = (ROOT / "templates/grow_device_cycles.html").read_text(encoding="utf-8")
    require("Alle Zyklen mit Belegen ansehen" in template and "Ereignis #{{ cycle.start_id }}" in drilldown, "Belegliste und Einzelpaare sind in der Oberfläche erreichbar")
    print("✅ INTELLIGENCE.CYCLE-EVIDENCE.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
