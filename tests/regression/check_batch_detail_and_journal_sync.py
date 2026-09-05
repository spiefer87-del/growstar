#!/usr/bin/env python3
"""Regression für Growstar 3.16.19 / PLANT.BATCH.1."""

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
    with tempfile.TemporaryDirectory(prefix="growstar-batch-detail-") as temp_dir:
        database.DB_FILE = Path(temp_dir) / "plants.db"
        try:
            database.init_plant_management_db()
            cultivar_id = database.save_cultivar({
                "code": "BATCH-TEST",
                "name": "Batch Test",
                "active": True,
            })
            batch_id = database.save_batch({
                "code": "GR-TEST-001",
                "name": "Detailtest",
                "started_on": "2026-09-05",
                "status": "active",
            })
            database.save_plant({
                "code": "PL-BATCH-A",
                "display_name": "Aktive Batchpflanze",
                "cultivar_id": cultivar_id,
                "batch_id": batch_id,
                "started_on": "2026-08-20",
                "current_stage": "vegetative",
                "status": "active",
            })
            database.save_plant({
                "code": "PL-BATCH-B",
                "display_name": "Historische Batchpflanze",
                "cultivar_id": cultivar_id,
                "batch_id": batch_id,
                "started_on": "2026-08-20",
                "current_stage": "flowering",
                "status": "archived",
            })

            batch = database.get_batch(batch_id)
            plants = database.list_plants(batch_id=batch_id)
            require(
                batch["plant_count"] == 2
                and batch["active_count"] == 1
                and batch["status_label"] == "Aktiv",
                "Das Durchgangsdetail liefert Gesamtzahl, Aktivzahl und Status",
            )
            require(
                {plant["code"] for plant in plants}
                == {"PL-BATCH-A", "PL-BATCH-B"},
                "Aktuelle und historische Pflanzen bleiben im Durchgang nachvollziehbar",
            )
        finally:
            database.DB_FILE = original_db_file

    routes = (ROOT / "routes" / "plant_management.py").read_text(encoding="utf-8")
    batches = (ROOT / "templates" / "plants" / "batches.html").read_text(
        encoding="utf-8"
    )
    detail = (ROOT / "templates" / "plants" / "batch_detail.html").read_text(
        encoding="utf-8"
    )
    form = (ROOT / "templates" / "plants" / "journal_form.html").read_text(
        encoding="utf-8"
    )
    journal = (ROOT / "templates" / "plants" / "journal.html").read_text(
        encoding="utf-8"
    )
    journal_detail = (
        ROOT / "templates" / "plants" / "journal_detail.html"
    ).read_text(encoding="utf-8")
    css = (ROOT / "static" / "css" / "plant-management.css").read_text(
        encoding="utf-8"
    )

    require(
        '@app.route("/pflanzenmanagement/durchgaenge/<int:batch_id>")' in routes
        and '"plants/batch_detail.html"' in routes
        and "plants=list_plants(batch_id=batch_id)" in routes
        and "list_journal_entries(batch_id=batch_id, limit=8)" in routes
        and '"/pflanzenmanagement/durchgaenge/<int:batch_id>/bearbeiten"' in routes,
        "Detail- und Bearbeitungsroute sind sauber voneinander getrennt",
    )
    require(
        'data-batch-href="{{ url_for(\'batch_detail\'' in batches
        and "pm-clickable-row" in batches
        and "event.key === \"Enter\"" in batches
        and "pm-row-open" in batches
        and ".pm-clickable-row" in css,
        "Die Durchgangstabelle öffnet Details per Klick und Tastatur",
    )
    require(
        "Pflanzen in diesem Durchgang" in detail
        and "batch.plant_count" in detail
        and "batch.active_count" in detail
        and "plant_detail" in detail
        and "plant_journal_new" in detail
        and "Letzte Betriebsereignisse" in detail,
        "Die Detailseite bündelt Bestand, Kennzahlen und Betriebsereignisse",
    )
    require(
        'id="journal-plant-select"' in form
        and 'id="journal-batch-select"' in form
        and 'data-batch-id="{{ plant.batch_id or \'\' }}"' in form
        and "function syncBatchPlants()" in form
        and "selectedBatchIds.has(option.dataset.batchId)" in form
        and "batchSelect.addEventListener(\"change\", syncBatchPlants)" in form
        and "syncBatchPlants();" in form,
        "Die Journal-Durchgangsauswahl markiert zugeordnete Pflanzen sofort",
    )
    require(
        "manualPlantIds" in form
        and "excludedAutomaticIds" in form
        and "aria-live=\"polite\"" in form,
        "Manuelle Pflanzenauswahl und verständliche Live-Rückmeldung bleiben erhalten",
    )
    batch_chip_link = "url_for('batch_detail', batch_id=batch.id)"
    require(
        batch_chip_link in journal and batch_chip_link in journal_detail,
        "Durchgangschips im Journal führen ebenfalls direkt zur Detailseite",
    )

    print("✅ Growstar 3.16.19 / PLANT.BATCH.1 vollständig geprüft")


if __name__ == "__main__":
    main()
