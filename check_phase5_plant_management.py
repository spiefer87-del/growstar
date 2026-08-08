import tempfile
from pathlib import Path

import plant_management.database as dbmod
from plant_management.database import (
    init_plant_management_db,
    save_cultivar,
    save_batch,
    save_plant,
    get_dashboard,
    get_stage_events,
    set_plant_stage,
)


with tempfile.TemporaryDirectory() as tmp:
    dbmod.DB_FILE = Path(tmp) / "test.db"
    init_plant_management_db()

    cultivar_id = save_cultivar(
        {
            "name": "Test Sorte",
            "breeder": "Growstar",
            "expected_veg_days": 28,
            "expected_flower_days": 56,
            "active": True,
        }
    )

    batch_id = save_batch(
        {
            "name": "Testdurchgang",
            "started_on": "2026-08-01",
        }
    )

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

    assert get_dashboard()["active_plant_count"] == 1
    assert len(get_stage_events(plant_id)) == 1

    set_plant_stage(
        plant_id,
        "flowering",
        started_on="2026-08-15",
        note="Test",
    )

    events = get_stage_events(plant_id)
    assert len(events) == 2
    assert events[0]["ended_on"] == "2026-08-15"
    assert events[1]["stage"] == "flowering"

print("✅ Pflanzenmanagement Datenmodell OK")
