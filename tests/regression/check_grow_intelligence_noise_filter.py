#!/usr/bin/env python3
"""Regression gegen Profilereignis-Fluten durch App-Neustarts."""

import tempfile
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import grow_events


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    original_db = grow_events.DB_FILE
    with tempfile.TemporaryDirectory(prefix="growstar-profile-noise-") as temp_dir:
        grow_events.DB_FILE = Path(temp_dir) / "events.db"
        try:
            grow_events.init_grow_event_db()
            boot_id = grow_events.record_event(
                station_id="tent_1",
                occurred_at=100,
                category="system",
                event_type="day_night_profile_changed",
                severity="info",
                title="Tagprofil aktiv",
                summary="Growstar hat beim Start das aktuell gültige Zeitfenster erkannt.",
                source="profile_scheduler",
                metadata={"vorher": "unbekannt", "aktiv": "TAG"},
            )
            transition_id = grow_events.record_event(
                station_id="tent_1",
                occurred_at=200,
                category="system",
                event_type="day_night_profile_changed",
                severity="info",
                title="Nachtprofil aktiv",
                summary="Growstar hat das aktive Zeitfenster anhand der Stationszeiten gewechselt.",
                source="profile_scheduler",
                metadata={"vorher": "TAG", "aktiv": "NACHT"},
            )
            manual_id = grow_events.record_event(
                station_id="tent_1",
                occurred_at=300,
                category="system",
                event_type="grow_profile_applied",
                severity="success",
                title="Grow-Profil aktiviert: Blüte",
                source="profile_manager",
            )

            visible = grow_events.list_events(
                station_id="tent_1", since=0, limit=20
            )
            visible_ids = {item["id"] for item in visible["items"]}
            require(
                boot_id not in visible_ids
                and transition_id in visible_ids
                and manual_id in visible_ids,
                "Timeline blendet nur die Start-Erkennung aus",
            )
            require(
                grow_events.event_summary(station_id="tent_1", since=0)["total"] == 2,
                "Kennzahlen ignorieren Profil- und technische Starteinträge",
            )
            analysis_ids = {
                item["id"] for item in grow_events.analysis_events(
                    station_id="tent_1", since=0
                )
            }
            require(
                boot_id not in analysis_ids
                and transition_id in analysis_ids
                and manual_id in analysis_ids,
                "Erkenntnislogik erhält ausschließlich echte Profilaktionen",
            )
            archived = grow_events.list_events(
                station_id="tent_1",
                since=0,
                limit=20,
                include_boot_profile_events=True,
            )
            require(
                boot_id in {item["id"] for item in archived["items"]},
                "Historische Start-Ereignisse bleiben gespeichert und abrufbar",
            )
        finally:
            grow_events.DB_FILE = original_db

    profile_source = (ROOT / "core/profile.py").read_text(encoding="utf-8")
    template = (ROOT / "templates/grow_events.html").read_text(encoding="utf-8")
    require(
        "if previous_profile is not None:" in profile_source
        and "beim Start das aktuell gültige Zeitfenster" not in profile_source,
        "Profilinitialisierung erzeugt künftig kein Ereignis",
    )
    require(
        "Technische Starteinträge ausgeblendet" in template,
        "Oberfläche erklärt den aktiven Rauschfilter",
    )

    print("✅ INTELLIGENCE.NOISE-FILTER.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
