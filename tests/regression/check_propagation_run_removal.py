#!/usr/bin/env python3
"""Regression fuer Growstar 3.16.28 / PLANT.PROPAGATION.1."""

from pathlib import Path
import sqlite3
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import plant_management.database as database
import plant_management.propagation as propagation


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    original_database_file = database.DB_FILE
    original_propagation_file = propagation.DB_FILE

    with tempfile.TemporaryDirectory(prefix="growstar-propagation-remove-") as temp_dir:
        db_file = Path(temp_dir) / "propagation.db"
        database.DB_FILE = db_file
        propagation.DB_FILE = db_file

        try:
            database.init_plant_management_db()
            propagation.init_propagation_db()

            cultivar_id = database.save_cultivar({
                "code": "REMOVE-CV",
                "name": "Korrektur-Sorte",
                "active": True,
            })
            lot_id = propagation.save_seed_lot(
                {
                    "code": "REMOVE-SEED",
                    "cultivar_id": cultivar_id,
                    "acquired_on": "2026-09-01",
                    "status": "available",
                },
                initial_quantity=4,
                user_id=7,
                user_name="Test",
            )

            run_id = propagation.create_propagation_run(
                {
                    "method": "seed",
                    "seed_lot_id": lot_id,
                    "target_count": 4,
                    "started_on": "2026-09-06",
                },
                user_id=7,
                user_name="Test",
            )
            require(
                propagation.seed_stock(lot_id) == 0
                and propagation.get_seed_lot(lot_id)["status"] == "depleted",
                "Der Samenansatz bucht den Bestand vor der Korrektur korrekt ab",
            )

            result = propagation.delete_propagation_run(run_id)
            with sqlite3.connect(db_file) as db:
                unit_count = db.execute(
                    "SELECT COUNT(*) FROM pm_propagation_units WHERE run_id = ?",
                    (run_id,),
                ).fetchone()[0]
                movement_count = db.execute(
                    """
                    SELECT COUNT(*) FROM pm_seed_movements
                    WHERE reference_type = 'propagation_run'
                      AND reference_id = ?
                    """,
                    (run_id,),
                ).fetchone()[0]

            require(
                result["removed_units"] == 4
                and result["restored_seed_count"] == 4
                and propagation.get_propagation_run(run_id) is None
                and unit_count == 0,
                "Ansatz und zugehoerige, ungenutzte Einheiten werden atomar entfernt",
            )
            require(
                propagation.seed_stock(lot_id) == 4
                and propagation.get_seed_lot(lot_id)["status"] == "available"
                and movement_count == 0,
                "Saatgutentnahme wird entfernt und der Lot-Status wieder freigegeben",
            )

            protected_run_id = propagation.create_propagation_run(
                {
                    "method": "seed",
                    "seed_lot_id": lot_id,
                    "target_count": 1,
                    "started_on": "2026-09-06",
                }
            )
            protected_run = propagation.get_propagation_run(protected_run_id)
            protected_unit = protected_run["units"][0]
            propagation.update_propagation_unit(
                protected_unit["id"],
                status="germinated",
                outcome_on="2026-09-06",
            )
            propagation.create_plant_from_propagation_unit(
                protected_unit["id"],
                display_name="Geschuetzte Pflanze",
            )

            try:
                propagation.delete_propagation_run(protected_run_id)
            except ValueError as exc:
                require(
                    "Herkunftskette" in str(exc)
                    and propagation.get_propagation_run(protected_run_id) is not None
                    and propagation.seed_stock(lot_id) == 3,
                    "Ansaetze mit erzeugten Pflanzen bleiben samt Saatgutbuchung geschuetzt",
                )
            else:
                raise AssertionError(
                    "Ansatz mit bereits erzeugter Pflanze wurde geloescht"
                )

            routes = (ROOT / "routes/plant_management.py").read_text(encoding="utf-8")
            detail = (
                ROOT / "templates/plants/propagation_run_detail.html"
            ).read_text(encoding="utf-8")
            require(
                "def propagation_run_remove(run_id):" in routes
                and '@permission_required("plants.edit")' in routes
                and 'request.form.get("confirm_code")' in routes
                and 'name="csrf_token"' in detail
                and 'name="confirm_code"' in detail
                and "Ansatz entfernen" in detail,
                "Route und Detailseite verlangen Rolle, CSRF-Schutz und Bestaetigung",
            )
            require(
                "plants.propagation_removed" in routes
                and "vermehrung,korrektur" in routes,
                "Entfernung bleibt in Audit und Betriebsjournal nachvollziehbar",
            )

            print(
                "✅ Growstar 3.16.28 / PLANT.PROPAGATION.1 vollstaendig geprueft"
            )
        finally:
            database.DB_FILE = original_database_file
            propagation.DB_FILE = original_propagation_file


if __name__ == "__main__":
    main()
