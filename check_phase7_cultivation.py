import tempfile
from pathlib import Path

import plant_management.database as plant_db
import plant_management.propagation as prop_db
import plant_management.journal as journal_db

from plant_management.database import (
    init_plant_management_db,
    save_cultivar,
    save_plant,
    get_plant,
    set_plant_stage,
)
from plant_management.propagation import (
    init_propagation_db,
    save_seed_lot,
    seed_stock,
    create_propagation_run,
    get_propagation_run,
    update_propagation_unit,
    create_plant_from_propagation_unit,
    get_plant_origin,
    save_genetic_line,
    get_genetic_line,
    set_plant_role,
    get_role_events,
    get_mother_summary,
    propagation_dashboard,
)
from plant_management.journal import (
    init_plant_journal_db,
    save_journal_entry,
    get_journal_entry,
)


with tempfile.TemporaryDirectory() as tmp:
    db_file = Path(tmp) / "test.db"

    plant_db.DB_FILE = db_file
    prop_db.DB_FILE = db_file
    journal_db.DB_FILE = db_file
    journal_db.UPLOAD_DIR = Path(tmp) / "journal_uploads"

    init_plant_management_db()
    init_propagation_db()
    init_plant_journal_db()

    cultivar_id = save_cultivar(
        {
            "name": "Test Cultivar",
            "breeder": "Growstar",
        }
    )

    # -----------------------------------------------------------------
    # Saatgut-Lot / Bewegungsbestand
    # -----------------------------------------------------------------
    lot_id = save_seed_lot(
        {
            "cultivar_id": cultivar_id,
            "supplier": "Test Supplier",
            "seed_type": "regular",
            "storage_location": "Box A",
        },
        initial_quantity=10,
        user_id=1,
        user_name="Admin",
    )

    assert seed_stock(lot_id) == 10

    seed_run_id = create_propagation_run(
        {
            "method": "seed",
            "seed_lot_id": lot_id,
            "target_count": 3,
            "name": "Seed Test",
            "started_on": "2026-08-09",
        },
        user_id=1,
        user_name="Admin",
    )

    assert seed_stock(lot_id) == 7

    seed_run = get_propagation_run(seed_run_id)
    assert seed_run["method"] == "seed"
    assert len(seed_run["units"]) == 3

    seed_unit = seed_run["units"][0]
    update_propagation_unit(
        seed_unit["id"],
        status="germinated",
        outcome_on="2026-08-11",
    )

    seed_plant_id = create_plant_from_propagation_unit(
        seed_unit["id"],
        display_name="Seed Plant A",
        user_id=1,
        user_name="Admin",
    )

    seed_plant = get_plant(seed_plant_id)
    assert seed_plant["current_stage"] == "seedling"
    assert seed_plant["current_role"] == "production"

    seed_origin = get_plant_origin(seed_plant_id)
    assert seed_origin["origin_type"] == "seed"
    assert seed_origin["seed_lot_id"] == lot_id

    # -----------------------------------------------------------------
    # Selektion / genetische Linie / Mutterpflanze
    # -----------------------------------------------------------------
    line_id = save_genetic_line(
        {
            "name": "Test Selection #1",
            "source_plant_id": seed_plant_id,
            "selection_type": "Selection",
            "selected_on": "2026-08-20",
        }
    )

    line = get_genetic_line(line_id)
    assert line["source_plant_id"] == seed_plant_id

    assert set_plant_role(
        seed_plant_id,
        "mother",
        started_on="2026-08-21",
        genetic_line_id=line_id,
        note="Zur Mutter bestimmt",
        user_id=1,
        user_name="Admin",
    ) is True

    mother = get_plant(seed_plant_id)
    assert mother["current_role"] == "mother"
    assert mother["genetic_line_id"] == line_id
    assert len(get_role_events(seed_plant_id)) >= 2

    # -----------------------------------------------------------------
    # Stecklingsansatz / klonale Herkunft
    # -----------------------------------------------------------------
    cutting_run_id = create_propagation_run(
        {
            "method": "cutting",
            "mother_plant_id": seed_plant_id,
            "target_count": 2,
            "name": "Cutting Test",
            "started_on": "2026-08-22",
        },
        user_id=1,
        user_name="Admin",
    )

    cutting_run = get_propagation_run(cutting_run_id)
    assert cutting_run["genetic_line_id"] == line_id
    assert len(cutting_run["units"]) == 2

    rooted_unit = cutting_run["units"][0]
    failed_unit = cutting_run["units"][1]

    update_propagation_unit(
        rooted_unit["id"],
        status="rooted",
        outcome_on="2026-08-30",
    )
    update_propagation_unit(
        failed_unit["id"],
        status="failed",
        outcome_on="2026-08-29",
    )

    clone_id = create_plant_from_propagation_unit(
        rooted_unit["id"],
        display_name="Clone A",
        user_id=1,
        user_name="Admin",
    )

    clone = get_plant(clone_id)
    assert clone["genetic_line_id"] == line_id
    assert clone["current_stage"] == "vegetative"

    clone_origin = get_plant_origin(clone_id)
    assert clone_origin["origin_type"] == "cutting"
    assert clone_origin["mother_plant_id"] == seed_plant_id
    assert clone_origin["genetic_line_id"] == line_id

    summary = get_mother_summary(seed_plant_id)
    assert summary["unit_count"] == 2
    assert summary["successful_units"] == 1
    assert summary["failed_units"] == 1
    assert summary["success_rate"] == 50.0

    # -----------------------------------------------------------------
    # Mutterpflanze darf wieder in normalen Lifecycle wechseln
    # -----------------------------------------------------------------
    assert set_plant_role(
        seed_plant_id,
        "production",
        started_on="2026-09-01",
        note="Mutterfunktion beendet",
        user_id=1,
        user_name="Admin",
    ) is True

    set_plant_stage(
        seed_plant_id,
        "flowering",
        started_on="2026-09-01",
        note="In Produktions-Lifecycle überführt",
        created_by=1,
    )

    transitioned = get_plant(seed_plant_id)
    assert transitioned["current_role"] == "production"
    assert transitioned["current_stage"] == "flowering"
    assert transitioned["genetic_line_id"] == line_id

    # Lebenszyklus kann anschließend sauber beendet werden.
    assert set_plant_role(
        seed_plant_id,
        "retired",
        started_on="2026-10-15",
        note="Lifecycle Ende",
        user_id=1,
        user_name="Admin",
    ) is True

    set_plant_stage(
        seed_plant_id,
        "finished",
        started_on="2026-10-15",
        note="Lifecycle Ende",
        created_by=1,
    )

    ended = get_plant(seed_plant_id)
    assert ended["current_role"] == "retired"
    assert ended["current_stage"] == "finished"
    assert ended["status"] == "finished"
    assert ended["genetic_line_id"] == line_id

    # -----------------------------------------------------------------
    # Systemjournal
    # -----------------------------------------------------------------
    journal_id = save_journal_entry(
        {
            "category": "care",
            "severity": "info",
            "title": "Automatisches Testereignis",
        },
        plant_ids=[clone_id],
        user_id=1,
        user_name="Admin",
        source="system",
    )

    journal_entry = get_journal_entry(journal_id)
    assert journal_entry["source"] == "system"

    stats = propagation_dashboard()
    assert stats["seed_stock"] == 7
    assert stats["germination_rate"] == 100.0
    assert stats["rooting_rate"] == 50.0

print("✅ Phase 7 Genetik/Saatgut/Vermehrung/Lifecycle OK")
