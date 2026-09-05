"""Speicheroptimierte Fotodokumentation für einzelne Pflanzen."""

from __future__ import annotations

import sqlite3
import time
import uuid
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

from .constants import STAGE_LABELS, STAGE_COLORS


DB_FILE = Path(__file__).resolve().parent.parent / "data.db"
PHOTO_DIR = Path(__file__).resolve().parent.parent / "instance" / "plant_photos"

MAX_SOURCE_BYTES = 12 * 1024 * 1024
MAX_IMAGE_EDGE = 1600
JPEG_QUALITY = 82


def _db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now():
    return int(time.time())


def _normalize_captured_at(value=None):
    if not value:
        captured = datetime.now()
    else:
        try:
            captured = datetime.fromisoformat(str(value).strip())
        except ValueError as exc:
            raise ValueError("Ungültiges Aufnahmedatum.") from exc

    captured = captured.replace(second=0, microsecond=0)
    if captured > datetime.now() + timedelta(minutes=5):
        raise ValueError("Das Aufnahmedatum darf nicht in der Zukunft liegen.")
    return captured.isoformat(timespec="minutes")


def init_plant_photo_db():
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    db = _db()
    try:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS pm_plant_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plant_id INTEGER NOT NULL,
                journal_entry_id INTEGER,
                stored_name TEXT NOT NULL UNIQUE,
                original_name TEXT NOT NULL,
                mime_type TEXT NOT NULL DEFAULT 'image/jpeg',
                size_bytes INTEGER NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                captured_at TEXT NOT NULL,
                stage TEXT NOT NULL,
                note TEXT,
                created_by INTEGER,
                created_by_name TEXT,
                created_at INTEGER NOT NULL,
                deleted_at INTEGER,
                deleted_by INTEGER,
                deleted_by_name TEXT,
                FOREIGN KEY(plant_id) REFERENCES pm_plants(id) ON DELETE CASCADE,
                FOREIGN KEY(journal_entry_id) REFERENCES pm_journal_entries(id)
            );

            CREATE INDEX IF NOT EXISTS idx_pm_plant_photos_plant_date
            ON pm_plant_photos(plant_id, captured_at DESC);

            CREATE INDEX IF NOT EXISTS idx_pm_plant_photos_journal
            ON pm_plant_photos(journal_entry_id);
            """
        )
        db.commit()
    finally:
        db.close()


def _prepare_image(upload):
    if not upload or not getattr(upload, "filename", None):
        raise ValueError("Bitte ein Foto aufnehmen oder auswählen.")

    content = upload.stream.read(MAX_SOURCE_BYTES + 1)
    if not content:
        raise ValueError("Das ausgewählte Foto ist leer.")
    if len(content) > MAX_SOURCE_BYTES:
        raise ValueError("Das Ausgangsfoto darf maximal 12 MB groß sein.")

    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError as exc:
        raise RuntimeError(
            "Die Bildverarbeitung ist nicht verfügbar (Python-Paket Pillow fehlt)."
        ) from exc

    try:
        with Image.open(BytesIO(content)) as source:
            if str(source.format or "").upper() not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Nicht unterstütztes Bildformat")
            source.load()
            image = ImageOps.exif_transpose(source)
            image.thumbnail(
                (MAX_IMAGE_EDGE, MAX_IMAGE_EDGE),
                Image.Resampling.LANCZOS,
            )

            if image.mode in {"RGBA", "LA"} or (
                image.mode == "P" and "transparency" in image.info
            ):
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")

            output = BytesIO()
            image.save(
                output,
                format="JPEG",
                quality=JPEG_QUALITY,
                optimize=True,
                progressive=True,
            )
            encoded = output.getvalue()
            width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError(
            "Die Datei ist kein gültiges JPG-, PNG- oder WEBP-Foto."
        ) from exc

    return encoded, int(width), int(height)


def _plant_and_stage(db, plant_id, captured_at):
    plant = db.execute(
        """
        SELECT p.id, p.code, p.display_name, p.started_on,
               p.current_stage, p.batch_id, c.name AS cultivar_name
        FROM pm_plants p
        LEFT JOIN pm_cultivars c ON c.id = p.cultivar_id
        WHERE p.id = ?
        """,
        (int(plant_id),),
    ).fetchone()
    if not plant:
        raise ValueError("Die ausgewählte Pflanze wurde nicht gefunden.")

    captured_on = captured_at[:10]
    if plant["started_on"] and captured_on < str(plant["started_on"])[:10]:
        raise ValueError(
            "Das Aufnahmedatum darf nicht vor dem Startdatum der Pflanze liegen."
        )

    event = db.execute(
        """
        SELECT stage
        FROM pm_stage_events
        WHERE plant_id = ? AND started_on <= ?
        ORDER BY started_on DESC, id DESC
        LIMIT 1
        """,
        (int(plant_id), captured_on),
    ).fetchone()
    stage = event["stage"] if event else plant["current_stage"]
    return dict(plant), stage


def save_plant_photo(
    plant_id,
    upload,
    *,
    captured_at=None,
    note=None,
    user_id=None,
    user_name=None,
):
    try:
        plant_id = int(plant_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Bitte eine gültige Pflanze auswählen.") from exc

    captured_at = _normalize_captured_at(captured_at)
    content, width, height = _prepare_image(upload)
    original_name = Path(upload.filename).name or "Pflanzenfoto"
    stored_name = f"{uuid.uuid4().hex}.jpg"
    target = PHOTO_DIR / stored_name

    db = _db()
    try:
        plant, stage = _plant_and_stage(db, plant_id, captured_at)
        target.write_bytes(content)
        cur = db.execute(
            """
            INSERT INTO pm_plant_photos (
                plant_id, stored_name, original_name, mime_type,
                size_bytes, width, height, captured_at, stage, note,
                created_by, created_by_name, created_at
            )
            VALUES (?, ?, ?, 'image/jpeg', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plant_id,
                stored_name,
                original_name,
                len(content),
                width,
                height,
                captured_at,
                stage,
                str(note or "").strip() or None,
                user_id,
                user_name,
                _now(),
            ),
        )
        db.commit()
        return {
            "id": int(cur.lastrowid),
            "plant": plant,
            "stage": stage,
            "stage_label": STAGE_LABELS.get(stage, stage),
            "captured_at": captured_at,
            "size_bytes": len(content),
            "width": width,
            "height": height,
        }
    except Exception:
        db.rollback()
        target.unlink(missing_ok=True)
        raise
    finally:
        db.close()


def link_photo_to_journal(photo_id, journal_entry_id):
    db = _db()
    try:
        db.execute(
            """
            UPDATE pm_plant_photos
            SET journal_entry_id = ?
            WHERE id = ? AND deleted_at IS NULL
            """,
            (int(journal_entry_id), int(photo_id)),
        )
        db.commit()
    finally:
        db.close()


def _decorate(row):
    if not row:
        return None
    item = dict(row)
    item["stage_label"] = STAGE_LABELS.get(item["stage"], item["stage"])
    item["stage_color"] = STAGE_COLORS.get(item["stage"], "#64748b")
    try:
        captured = datetime.fromisoformat(item["captured_at"])
        item["captured_date"] = captured.strftime("%d.%m.%Y")
        item["captured_time"] = captured.strftime("%H:%M")
    except (TypeError, ValueError):
        item["captured_date"] = str(item.get("captured_at") or "")[:10]
        item["captured_time"] = ""
    item["size_kb"] = max(1, round(int(item["size_bytes"]) / 1024))
    item["path"] = str(PHOTO_DIR / item["stored_name"])
    return item


def list_plant_photos(*, plant_id=None, journal_entry_id=None, stage=None, limit=250):
    where = ["ph.deleted_at IS NULL"]
    params = []
    if plant_id:
        where.append("ph.plant_id = ?")
        params.append(int(plant_id))
    if journal_entry_id:
        where.append("ph.journal_entry_id = ?")
        params.append(int(journal_entry_id))
    if stage:
        where.append("ph.stage = ?")
        params.append(str(stage))

    params.append(max(1, min(int(limit), 1000)))
    db = _db()
    try:
        rows = db.execute(
            f"""
            SELECT ph.*, p.code AS plant_code,
                   p.display_name AS plant_name,
                   c.name AS cultivar_name
            FROM pm_plant_photos ph
            JOIN pm_plants p ON p.id = ph.plant_id
            LEFT JOIN pm_cultivars c ON c.id = p.cultivar_id
            WHERE {' AND '.join(where)}
            ORDER BY ph.captured_at DESC, ph.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [_decorate(row) for row in rows]
    finally:
        db.close()


def get_plant_photo(photo_id):
    db = _db()
    try:
        row = db.execute(
            """
            SELECT ph.*, p.code AS plant_code,
                   p.display_name AS plant_name,
                   c.name AS cultivar_name
            FROM pm_plant_photos ph
            JOIN pm_plants p ON p.id = ph.plant_id
            LEFT JOIN pm_cultivars c ON c.id = p.cultivar_id
            WHERE ph.id = ? AND ph.deleted_at IS NULL
            """,
            (int(photo_id),),
        ).fetchone()
        return _decorate(row)
    finally:
        db.close()


def remove_plant_photo(photo_id, *, user_id=None, user_name=None):
    db = _db()
    try:
        row = db.execute(
            """
            SELECT stored_name
            FROM pm_plant_photos
            WHERE id = ? AND deleted_at IS NULL
            """,
            (int(photo_id),),
        ).fetchone()
        if not row:
            return False
        db.execute(
            """
            UPDATE pm_plant_photos
            SET deleted_at = ?, deleted_by = ?, deleted_by_name = ?
            WHERE id = ?
            """,
            (_now(), user_id, user_name, int(photo_id)),
        )
        db.commit()
        try:
            (PHOTO_DIR / row["stored_name"]).unlink(missing_ok=True)
        except OSError:
            pass
        return True
    finally:
        db.close()


def photo_markers_for_timeline(timeline):
    if not timeline.get("rows"):
        return timeline
    start = date.fromisoformat(timeline["start"])
    total_days = max(1, int(timeline["total_days"]))
    photos = list_plant_photos(limit=1000)
    by_plant = {}
    for photo in photos:
        by_plant.setdefault(photo["plant_id"], []).append(photo)

    for row in timeline["rows"]:
        markers = []
        for photo in by_plant.get(row["plant"]["id"], []):
            captured_on = date.fromisoformat(photo["captured_at"][:10])
            left = ((captured_on - start).days / total_days) * 100
            if 0 <= left <= 100:
                markers.append({**photo, "left": round(left, 3)})
        row["photo_markers"] = markers
    return timeline
