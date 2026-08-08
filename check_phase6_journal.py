import tempfile
from pathlib import Path

import plant_management.database as plant_db
import plant_management.journal as journal_db

from plant_management.database import (
    init_plant_management_db,
    save_cultivar,
    save_batch,
    save_plant,
)
from plant_management.journal import (
    init_plant_journal_db,
    save_journal_entry,
    get_journal_entry,
    list_journal_entries,
    journal_stats,
    resolve_follow_up,
    cancel_journal_entry,
    measurements_from_form,
    get_revisions,
)


with tempfile.TemporaryDirectory() as tmp:
    test_db = Path(tmp) / "test.db"

    plant_db.DB_FILE = test_db
    journal_db.DB_FILE = test_db
    journal_db.UPLOAD_DIR = Path(tmp) / "uploads"

    init_plant_management_db()
    init_plant_journal_db()

    cultivar_id = save_cultivar({"name": "Test Sorte"})
    batch_id = save_batch({"name": "Test Grow", "started_on": "2026-08-01"})
    plant_id = save_plant(
        {
            "display_name": "A01",
            "cultivar_id": cultivar_id,
            "batch_id": batch_id,
            "started_on": "2026-08-01",
            "current_stage": "vegetative",
            "status": "active",
        }
    )

    measurements = measurements_from_form(
        {
            "measurement_temperature": "24,5",
            "measurement_humidity": "61",
            "measurement_ph": "6.2",
        }
    )

    entry_id = save_journal_entry(
        {
            "occurred_at": "2026-08-09T00:30",
            "category": "observation",
            "severity": "attention",
            "title": "Kontrolle",
            "body": "Alles geprüft.",
            "follow_up_required": "1",
            "follow_up_due_on": "2026-08-10",
        },
        plant_ids=[plant_id],
        batch_ids=[batch_id],
        measurements=measurements,
        user_id=1,
        user_name="Admin",
    )

    entry = get_journal_entry(entry_id)
    assert entry["title"] == "Kontrolle"
    assert len(entry["plants"]) == 1
    assert len(entry["batches"]) == 1
    assert len(entry["measurements"]) == 3
    assert entry["is_open_follow_up"] is True

    save_journal_entry(
        {
            "occurred_at": "2026-08-09T00:31",
            "category": "observation",
            "severity": "info",
            "title": "Kontrolle aktualisiert",
            "body": "Revisionstest",
        },
        entry_id=entry_id,
        plant_ids=[plant_id],
        batch_ids=[batch_id],
        measurements=[],
        user_id=1,
        user_name="Admin",
    )

    assert len(get_revisions(entry_id)) == 1

    entries = list_journal_entries(plant_id=plant_id)
    assert len(entries) == 1

    stats = journal_stats()
    assert stats["seven_day_count"] >= 0

    # Nach dem Edit wurde follow_up_required absichtlich entfernt; neues
    # Follow-up zum Resolve-Test setzen.
    second_id = save_journal_entry(
        {
            "occurred_at": "2026-08-09T00:40",
            "category": "issue",
            "severity": "critical",
            "title": "Follow-up Test",
            "follow_up_required": "1",
        },
        plant_ids=[plant_id],
        user_id=1,
        user_name="Admin",
    )

    assert resolve_follow_up(second_id, user_id=1, user_name="Admin") is True
    assert get_journal_entry(second_id)["is_resolved"] is True

    assert cancel_journal_entry(
        entry_id,
        reason="Teststorno",
        user_id=1,
        user_name="Admin",
    ) is True
    assert get_journal_entry(entry_id)["is_cancelled"] is True

print("✅ Betriebsjournal Datenmodell OK")
