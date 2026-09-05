#!/usr/bin/env python3
"""Regression für Growstar 3.16.24 / PLANT.LIFECYCLE.2."""

from datetime import date, timedelta
from pathlib import Path
import tempfile
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import plant_management.database as database


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    original_db_file = database.DB_FILE
    with tempfile.TemporaryDirectory(prefix="growstar-stage-correction-") as temp_dir:
        database.DB_FILE = Path(temp_dir) / "plants.db"
        try:
            database.init_plant_management_db()
            cultivar_id = database.save_cultivar({
                "code": "FLOWER-63",
                "name": "Flower 63",
                "expected_flower_days": 63,
                "active": True,
            })
            plant_id = database.save_plant({
                "code": "PL-CORRECT",
                "display_name": "Korrekturpflanze",
                "cultivar_id": cultivar_id,
                "started_on": "2026-08-02",
                "current_stage": "vegetative",
                "status": "active",
            })
            database.set_plant_stage(
                plant_id,
                "flowering",
                started_on="2026-09-05",
                note="Blüte zunächst zu spät erfasst",
            )

            correction = database.correct_current_stage_start(
                plant_id,
                "2026-08-31",
                note="Kalender geprüft",
            )
            events = database.get_stage_events(plant_id)
            plant = database.get_plant(plant_id)
            require(
                correction["event_id"] == events[1]["id"]
                and correction["stage"] == "flowering"
                and correction["old_started_on"] == "2026-09-05"
                and correction["new_started_on"] == "2026-08-31"
                and correction["previous_stage"] == "vegetative"
                and correction["following_stage"] is None,
                "Die bestätigte Korrektur meldet alte und neue Phasengrenze zurück",
            )
            require(
                events[0]["stage"] == "vegetative"
                and events[0]["ended_on"] == "2026-08-31"
                and events[1]["stage"] == "flowering"
                and events[1]["started_on"] == "2026-08-31"
                and events[1]["ended_on"] is None,
                "Vorherige und aktuelle Phase teilen nach der Korrektur dieselbe Grenze",
            )
            require(
                plant["current_stage_started_on"] == "2026-08-31"
                and plant["flowering_started_on"] == "2026-08-31"
                and plant["harvest_forecast"]["harvest_on"] == "2026-11-02",
                "Pflanzendetail und Ernteprognose verwenden sofort den korrigierten Blütestart",
            )
            require(
                "Datumskorrektur: Kalender geprüft" in events[1]["note"],
                "Eine eingegebene Begründung bleibt am Phasenereignis nachvollziehbar",
            )

            vegetative_event_id = events[0]["id"]
            historical = database.correct_stage_event_start(
                plant_id,
                vegetative_event_id,
                "2026-07-28",
                note="Vegetationsbeginn im Kalender korrigiert",
            )
            events = database.get_stage_events(plant_id)
            plant = database.get_plant(plant_id)
            require(
                historical["stage"] == "vegetative"
                and historical["old_started_on"] == "2026-08-02"
                and historical["new_started_on"] == "2026-07-28"
                and historical["following_stage"] == "flowering"
                and events[0]["started_on"] == "2026-07-28"
                and events[0]["ended_on"] == "2026-08-31"
                and plant["started_on"] == "2026-07-28",
                "Auch eine abgeschlossene historische Phase kann direkt korrigiert werden",
            )
            require(
                database.correct_stage_event_start(
                    plant_id,
                    vegetative_event_id,
                    "2026-07-28",
                ) is None,
                "Ein unverändertes historisches Startdatum erzeugt keine Scheinkorrektur",
            )

            try:
                database.correct_stage_event_start(
                    plant_id,
                    vegetative_event_id,
                    "2026-09-01",
                )
            except ValueError as exc:
                after_following_rejected = "nächsten Phase" in str(exc)
            else:
                after_following_rejected = False
            require(
                after_following_rejected
                and database.get_stage_events(plant_id)[0]["started_on"] == "2026-07-28",
                "Eine historische Phase darf nicht hinter den Beginn ihrer Folgephase rutschen",
            )
            require(
                database.correct_current_stage_start(plant_id, "2026-08-31") is None,
                "Ein unverändertes Startdatum erzeugt keine Scheinkorrektur",
            )

            try:
                database.correct_current_stage_start(plant_id, "2026-07-27")
            except ValueError as exc:
                before_previous_rejected = "vor dem Beginn der vorherigen Phase" in str(exc)
            else:
                before_previous_rejected = False
            require(
                before_previous_rejected
                and database.get_plant(plant_id)["current_stage_started_on"] == "2026-08-31",
                "Eine Korrektur vor die vorherige Phase wird ohne Teiländerung abgewiesen",
            )

            tomorrow = (date.today() + timedelta(days=1)).isoformat()
            try:
                database.correct_current_stage_start(plant_id, tomorrow)
            except ValueError as exc:
                future_rejected = "nicht in der Zukunft" in str(exc)
            else:
                future_rejected = False
            require(
                future_rejected,
                "Ein zukünftiger Beginn einer bereits laufenden Phase ist nicht zulässig",
            )
        finally:
            database.DB_FILE = original_db_file

    route = (ROOT / "routes" / "plant_management.py").read_text(encoding="utf-8")
    detail = (ROOT / "templates" / "plants" / "plant_detail.html").read_text(
        encoding="utf-8"
    )
    require(
        'request.form.get("confirm_stage_date_correction") != "1"' in route
        and '"plants.stage_start_corrected"' in route
        and "correct_stage_event_start(" in route
        and "def plant_stage_start_correct(" in route
        and "Phasenstart korrigiert:" in route,
        "Eigene Route verlangt Berechtigung und Bestätigung und dokumentiert jede Korrektur",
    )
    require(
        'id="plant-stage-form"' in detail
        and "plant_stage_start_correct" in detail
        and 'id="phase-{{ event.id }}"' in detail
        and 'name="confirm_stage_date_correction"' in detail
        and "Startdatum der Phase" in detail
        and "Angrenzende Phasengrenzen" in detail
        and "Phase wechseln oder korrigieren" not in detail
        and "Bereits gespeicherte Startdaten" in detail,
        "Jede Verlaufphase hat ihren eigenen Ändern-Dialog; die Steuerung bleibt ein reiner Phasenwechsel",
    )

    print("✅ Growstar 3.16.24 / PLANT.LIFECYCLE.2 vollständig geprüft")


if __name__ == "__main__":
    main()
