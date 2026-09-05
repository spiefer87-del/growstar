#!/usr/bin/env python3
"""Regression für Growstar 3.16.22 / PLANT.PHOTO.2."""

from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import tempfile
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from PIL import Image

import plant_management.database as database
import plant_management.journal as journal
import plant_management.photos as photos


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def make_upload():
    source = Image.effect_noise((2400, 1800), 90).convert("RGB")
    stream = BytesIO()
    source.save(stream, format="JPEG", quality=96)
    content = stream.getvalue()
    return SimpleNamespace(
        filename="kamera-original.jpg",
        stream=BytesIO(content),
    ), len(content)


def main():
    original_database_file = database.DB_FILE
    original_journal_file = journal.DB_FILE
    original_journal_dir = journal.UPLOAD_DIR
    original_photo_file = photos.DB_FILE
    original_photo_dir = photos.PHOTO_DIR

    with tempfile.TemporaryDirectory(prefix="growstar-photos-") as temp_dir:
        temp = Path(temp_dir)
        db_file = temp / "photos.db"
        database.DB_FILE = db_file
        journal.DB_FILE = db_file
        journal.UPLOAD_DIR = temp / "journal"
        photos.DB_FILE = db_file
        photos.PHOTO_DIR = temp / "plant_photos"

        try:
            database.init_plant_management_db()
            journal.init_plant_journal_db()
            require(
                photos.list_plant_photos() == [],
                "Der Foto-Lesepfad legt eine nach dem Upgrade fehlende Tabelle selbst an",
            )

            cultivar_id = database.save_cultivar({
                "code": "PHOTO-CULTIVAR",
                "name": "Foto-Sorte",
                "active": True,
            })
            plant_id = database.save_plant({
                "code": "PL-PHOTO",
                "display_name": "Fotopflanze",
                "cultivar_id": cultivar_id,
                "started_on": "2026-08-01",
                "current_stage": "vegetative",
                "status": "active",
            })
            database.set_plant_stage(
                plant_id,
                "flowering",
                started_on="2026-09-01",
            )

            upload, source_size = make_upload()
            saved = photos.save_plant_photo(
                plant_id,
                upload,
                captured_at="2026-09-02T18:30",
                note="Blüte dokumentiert",
                user_id=7,
                user_name="Test",
            )
            photo = photos.get_plant_photo(saved["id"])

            require(
                photo
                and photo["stage"] == "flowering"
                and photo["captured_at"] == "2026-09-02T18:30",
                "Aufnahmezeit und die damals gültige Pflanzenphase werden gespeichert",
            )
            require(
                max(photo["width"], photo["height"]) == photos.MAX_IMAGE_EDGE
                and photo["mime_type"] == "image/jpeg"
                and photo["size_bytes"] < source_size,
                "Das Kamerafoto wird auf 1600 Pixel verkleinert und platzsparend kodiert",
            )
            with Image.open(photo["path"]) as stored:
                require(
                    stored.format == "JPEG" and stored.mode == "RGB",
                    "Das gespeicherte Bild ist ein browserkompatibles, bereinigtes JPEG",
                )

            entry_id = journal.save_journal_entry(
                {
                    "occurred_at": saved["captured_at"],
                    "category": "observation",
                    "severity": "info",
                    "title": "Pflanzenfoto: Fotopflanze",
                    "body": "Blüte dokumentiert",
                    "tags": "foto,flowering",
                },
                plant_ids=[plant_id],
                source="system",
            )
            photos.link_photo_to_journal(saved["id"], entry_id)
            require(
                photos.list_plant_photos(journal_entry_id=entry_id)[0]["id"]
                == saved["id"],
                "Foto und Betriebsjournal-Eintrag sind direkt miteinander verknüpft",
            )

            timeline = photos.photo_markers_for_timeline(
                database.get_timeline(active_only=True)
            )
            require(
                timeline["rows"][0]["photo_markers"][0]["id"] == saved["id"],
                "Die Lifecycle-Timeline erhält einen klickbaren Marker für das Foto",
            )

            future_upload, _ = make_upload()
            try:
                photos.save_plant_photo(
                    plant_id,
                    future_upload,
                    captured_at=(date.today() + timedelta(days=1)).isoformat() + "T12:00",
                )
            except ValueError as exc:
                require(
                    "Zukunft" in str(exc),
                    "Zukünftige Aufnahmezeitpunkte werden abgewiesen",
                )
            else:
                raise AssertionError("Zukünftiges Aufnahmedatum wurde akzeptiert")

            stored_path = Path(photo["path"])
            require(
                photos.remove_plant_photo(saved["id"], user_id=7)
                and not stored_path.exists()
                and photos.get_plant_photo(saved["id"]) is None,
                "Entfernte Fotos verschwinden aus Ansicht und Dateispeicher",
            )

            routes_source = (ROOT / "routes/plant_management.py").read_text(encoding="utf-8")
            dashboard_source = (ROOT / "templates/plants/dashboard.html").read_text(encoding="utf-8")
            timeline_source = (ROOT / "templates/plants/timeline.html").read_text(encoding="utf-8")
            require(
                'name="camera_photo"' in (
                    photo_form_source := (
                        ROOT / "templates/plants/photo_form.html"
                    ).read_text(encoding="utf-8")
                )
                and 'capture="environment"' in photo_form_source
                and 'name="file_photo"' in photo_form_source
                and 'Datei oder Galerie auswählen' in photo_form_source
                and "＋ Fotos" in dashboard_source
                and "pm-photo-marker" in timeline_source
                and "plant_photo_manager" in routes_source,
                "Dashboard, Kameraaufnahme, Foto-Manager und Timeline sind verdrahtet",
            )
            print("✅ Growstar 3.16.22 / PLANT.PHOTO.2 vollständig geprüft")
        finally:
            database.DB_FILE = original_database_file
            journal.DB_FILE = original_journal_file
            journal.UPLOAD_DIR = original_journal_dir
            photos.DB_FILE = original_photo_file
            photos.PHOTO_DIR = original_photo_dir


if __name__ == "__main__":
    main()
