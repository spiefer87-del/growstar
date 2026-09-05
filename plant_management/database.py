import sqlite3
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from .constants import (
    STAGE_LABELS,
    STAGE_COLORS,
    PLANT_STATUS_LABELS,
    BATCH_STATUS_LABELS,
    PLANT_ROLE_LABELS,
)

DB_FILE = Path(__file__).resolve().parent.parent / "data.db"


def _db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now():
    return int(time.time())


def _table_exists(db, table):
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row)


def _text(value):
    if value is None:
        return ""
    return str(value).strip()


def _iso_date(value=None):
    if not value:
        return date.today().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _days_between(start, end=None):
    if not start:
        return None
    try:
        start_d = date.fromisoformat(str(start)[:10])
        end_d = date.fromisoformat(str(end)[:10]) if end else date.today()
        return max(0, (end_d - start_d).days)
    except Exception:
        return None


def calculate_harvest_forecast(
    flowering_started_on,
    expected_flower_days,
    *,
    today=None,
):
    """Ermittelt die dynamische Ernteprognose aus Blütestart und Sortenwert.

    Der Sortenwert beschreibt die geplante Dauer der Blüte. Die Prognose wird
    bewusst nicht aus dem Anlagedatum der Pflanze geraten: Ohne dokumentierten
    Blütebeginn fehlt der verlässliche Startpunkt und es wird ``None`` geliefert.
    """

    if not flowering_started_on:
        return None

    try:
        flower_start = date.fromisoformat(str(flowering_started_on)[:10])
        flower_days = int(expected_flower_days)
        reference = today or date.today()
        if isinstance(reference, datetime):
            reference = reference.date()
        elif not isinstance(reference, date):
            reference = date.fromisoformat(str(reference)[:10])
    except (TypeError, ValueError):
        return None

    if flower_days <= 0:
        return None

    harvest_on = flower_start + timedelta(days=flower_days)
    days_remaining = (harvest_on - reference).days
    elapsed_days = max(0, (reference - flower_start).days)
    flower_day = elapsed_days + 1 if reference >= flower_start else 0
    progress = max(0.0, min(1.0, elapsed_days / flower_days))

    if days_remaining > 0:
        status_text = f"noch {days_remaining} Tage"
    elif days_remaining == 0:
        status_text = "heute"
    else:
        status_text = f"seit {abs(days_remaining)} Tagen fällig"

    return {
        "flowering_started_on": flower_start.isoformat(),
        "flowering_started_label": flower_start.strftime("%d.%m.%Y"),
        "harvest_on": harvest_on.isoformat(),
        "harvest_label": harvest_on.strftime("%d.%m.%Y"),
        "expected_flower_days": flower_days,
        "days_remaining": days_remaining,
        "flower_day": flower_day,
        "progress": round(progress, 4),
        "progress_percent": round(progress * 100.0, 1),
        "overdue": days_remaining < 0,
        "status_text": status_text,
    }


def init_plant_management_db():
    db = _db()
    try:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS pm_cultivars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                breeder TEXT,
                genetics TEXT,
                growth_type TEXT,
                sativa_pct INTEGER,
                indica_pct INTEGER,
                expected_veg_days INTEGER,
                expected_flower_days INTEGER,
                description TEXT,
                tags TEXT,
                notes TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_pm_cultivars_name
            ON pm_cultivars(name);

            CREATE INDEX IF NOT EXISTS idx_pm_cultivars_active
            ON pm_cultivars(active);

            CREATE TABLE IF NOT EXISTS pm_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                location TEXT,
                started_on TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                notes TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_pm_batches_status
            ON pm_batches(status);

            CREATE TABLE IF NOT EXISTS pm_plants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                cultivar_id INTEGER,
                batch_id INTEGER,
                location TEXT,
                started_on TEXT NOT NULL,
                current_stage TEXT NOT NULL DEFAULT 'germination',
                status TEXT NOT NULL DEFAULT 'active',
                notes TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY(cultivar_id) REFERENCES pm_cultivars(id),
                FOREIGN KEY(batch_id) REFERENCES pm_batches(id)
            );

            CREATE INDEX IF NOT EXISTS idx_pm_plants_status
            ON pm_plants(status);

            CREATE INDEX IF NOT EXISTS idx_pm_plants_stage
            ON pm_plants(current_stage);

            CREATE INDEX IF NOT EXISTS idx_pm_plants_cultivar
            ON pm_plants(cultivar_id);

            CREATE INDEX IF NOT EXISTS idx_pm_plants_batch
            ON pm_plants(batch_id);

            CREATE TABLE IF NOT EXISTS pm_stage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plant_id INTEGER NOT NULL,
                stage TEXT NOT NULL,
                started_on TEXT NOT NULL,
                ended_on TEXT,
                note TEXT,
                created_by INTEGER,
                created_at INTEGER NOT NULL,
                FOREIGN KEY(plant_id) REFERENCES pm_plants(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_pm_stage_events_plant
            ON pm_stage_events(plant_id, started_on);
            """
        )
        db.commit()
    finally:
        db.close()


def _next_code(db, table, prefix, width=4):
    row = db.execute(
        f"SELECT id FROM {table} ORDER BY id DESC LIMIT 1"
    ).fetchone()
    next_id = (row["id"] if row else 0) + 1
    return f"{prefix}-{next_id:0{width}d}"


# ---------------------------------------------------------------------
# Sortenstamm
# ---------------------------------------------------------------------

def list_cultivars(include_inactive=True, search=None):
    db = _db()
    try:
        where = []
        params = []

        if not include_inactive:
            where.append("active = 1")

        if search:
            q = f"%{search.strip()}%"
            where.append(
                "(name LIKE ? OR code LIKE ? OR breeder LIKE ? OR genetics LIKE ? OR tags LIKE ?)"
            )
            params.extend([q, q, q, q, q])

        sql = "SELECT * FROM pm_cultivars"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY active DESC, name COLLATE NOCASE"

        return [dict(row) for row in db.execute(sql, params).fetchall()]
    finally:
        db.close()


def get_cultivar(cultivar_id):
    db = _db()
    try:
        row = db.execute(
            "SELECT * FROM pm_cultivars WHERE id = ?",
            (cultivar_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def get_cultivar_by_code(code):
    if not code:
        return None
    db = _db()
    try:
        row = db.execute(
            "SELECT * FROM pm_cultivars WHERE code = ? COLLATE NOCASE",
            (code.strip(),),
        ).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def save_cultivar(data, cultivar_id=None):
    db = _db()
    try:
        now = _now()
        code = _text(data.get("code"))
        if not code:
            code = _next_code(db, "pm_cultivars", "CV")

        payload = {
            "code": code.upper(),
            "name": _text(data.get("name")),
            "breeder": _text(data.get("breeder")) or None,
            "genetics": _text(data.get("genetics")) or None,
            "growth_type": _text(data.get("growth_type")) or None,
            "sativa_pct": _to_int(data.get("sativa_pct")),
            "indica_pct": _to_int(data.get("indica_pct")),
            "expected_veg_days": _to_int(data.get("expected_veg_days")),
            "expected_flower_days": _to_int(data.get("expected_flower_days")),
            "description": _text(data.get("description")) or None,
            "tags": _text(data.get("tags")) or None,
            "notes": _text(data.get("notes")) or None,
            "active": 1 if _truthy(data.get("active", True)) else 0,
        }

        if not payload["name"]:
            raise ValueError("Der Sortenname darf nicht leer sein.")

        for key in ("sativa_pct", "indica_pct"):
            value = payload[key]
            if value is not None and not 0 <= value <= 100:
                raise ValueError(f"{key} muss zwischen 0 und 100 liegen.")

        if cultivar_id:
            db.execute(
                """
                UPDATE pm_cultivars SET
                    code = :code,
                    name = :name,
                    breeder = :breeder,
                    genetics = :genetics,
                    growth_type = :growth_type,
                    sativa_pct = :sativa_pct,
                    indica_pct = :indica_pct,
                    expected_veg_days = :expected_veg_days,
                    expected_flower_days = :expected_flower_days,
                    description = :description,
                    tags = :tags,
                    notes = :notes,
                    active = :active,
                    updated_at = :updated_at
                WHERE id = :id
                """,
                {
                    **payload,
                    "updated_at": now,
                    "id": int(cultivar_id),
                },
            )
            saved_id = int(cultivar_id)
        else:
            cur = db.execute(
                """
                INSERT INTO pm_cultivars (
                    code, name, breeder, genetics, growth_type,
                    sativa_pct, indica_pct,
                    expected_veg_days, expected_flower_days,
                    description, tags, notes, active,
                    created_at, updated_at
                )
                VALUES (
                    :code, :name, :breeder, :genetics, :growth_type,
                    :sativa_pct, :indica_pct,
                    :expected_veg_days, :expected_flower_days,
                    :description, :tags, :notes, :active,
                    :created_at, :updated_at
                )
                """,
                {
                    **payload,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            saved_id = cur.lastrowid

        db.commit()
        return saved_id
    finally:
        db.close()


def upsert_cultivar_by_code(data):
    code = _text(data.get("code"))
    existing = get_cultivar_by_code(code) if code else None
    if existing:
        return save_cultivar(data, existing["id"]), "updated"
    return save_cultivar(data), "created"


# ---------------------------------------------------------------------
# Durchgänge / Batches
# ---------------------------------------------------------------------

def list_batches(include_archived=True):
    db = _db()
    try:
        sql = """
            SELECT b.*,
                   COUNT(p.id) AS plant_count,
                   SUM(CASE WHEN p.status = 'active' THEN 1 ELSE 0 END) AS active_count
            FROM pm_batches b
            LEFT JOIN pm_plants p ON p.batch_id = b.id
        """
        params = []
        if not include_archived:
            sql += " WHERE b.status != 'archived'"
        sql += " GROUP BY b.id ORDER BY b.started_on DESC, b.id DESC"

        rows = []
        for row in db.execute(sql, params).fetchall():
            item = dict(row)
            item["status_label"] = BATCH_STATUS_LABELS.get(
                item["status"], item["status"]
            )
            rows.append(item)
        return rows
    finally:
        db.close()


def get_batch(batch_id):
    db = _db()
    try:
        row = db.execute(
            """
            SELECT b.*,
                   COUNT(p.id) AS plant_count,
                   SUM(CASE WHEN p.status = 'active' THEN 1 ELSE 0 END) AS active_count
            FROM pm_batches b
            LEFT JOIN pm_plants p ON p.batch_id = b.id
            WHERE b.id = ?
            GROUP BY b.id
            """,
            (batch_id,),
        ).fetchone()
        if not row:
            return None

        item = dict(row)
        item["status_label"] = BATCH_STATUS_LABELS.get(
            item["status"], item["status"]
        )
        return item
    finally:
        db.close()


def save_batch(data, batch_id=None):
    db = _db()
    try:
        now = _now()
        code = _text(data.get("code"))
        if not code:
            code = _next_code(db, "pm_batches", f"GR-{date.today().year}", 3)

        payload = {
            "code": code.upper(),
            "name": _text(data.get("name")),
            "location": _text(data.get("location")) or None,
            "started_on": _iso_date(data.get("started_on")),
            "status": _text(data.get("status")) or "active",
            "notes": _text(data.get("notes")) or None,
        }

        if not payload["name"]:
            raise ValueError("Der Name des Durchgangs darf nicht leer sein.")

        if batch_id:
            db.execute(
                """
                UPDATE pm_batches SET
                    code=:code, name=:name, location=:location,
                    started_on=:started_on, status=:status,
                    notes=:notes, updated_at=:updated_at
                WHERE id=:id
                """,
                {**payload, "updated_at": now, "id": int(batch_id)},
            )
            saved_id = int(batch_id)
        else:
            cur = db.execute(
                """
                INSERT INTO pm_batches (
                    code, name, location, started_on, status, notes,
                    created_at, updated_at
                )
                VALUES (
                    :code, :name, :location, :started_on, :status, :notes,
                    :created_at, :updated_at
                )
                """,
                {**payload, "created_at": now, "updated_at": now},
            )
            saved_id = cur.lastrowid

        db.commit()
        return saved_id
    finally:
        db.close()


# ---------------------------------------------------------------------
# Pflanzen / WIP
# ---------------------------------------------------------------------

PLANT_SELECT = """
    SELECT
        p.*,
        c.code AS cultivar_code,
        c.name AS cultivar_name,
        c.breeder AS cultivar_breeder,
        c.expected_veg_days,
        c.expected_flower_days,
        b.code AS batch_code,
        b.name AS batch_name,
        (
            SELECT e.started_on
            FROM pm_stage_events e
            WHERE e.plant_id = p.id AND e.ended_on IS NULL
            ORDER BY e.started_on DESC, e.id DESC
            LIMIT 1
        ) AS current_stage_started_on,
        (
            SELECT e.started_on
            FROM pm_stage_events e
            WHERE e.plant_id = p.id AND e.stage = 'flowering'
            ORDER BY e.started_on DESC, e.id DESC
            LIMIT 1
        ) AS flowering_started_on
    FROM pm_plants p
    LEFT JOIN pm_cultivars c ON c.id = p.cultivar_id
    LEFT JOIN pm_batches b ON b.id = p.batch_id
"""


def _decorate_plant(item):
    item["stage_label"] = STAGE_LABELS.get(
        item.get("current_stage"), item.get("current_stage")
    )
    item["stage_color"] = STAGE_COLORS.get(
        item.get("current_stage"), "#64748b"
    )
    item["status_label"] = PLANT_STATUS_LABELS.get(
        item.get("status"), item.get("status")
    )
    role = item.get("current_role") or "production"
    item["role_label"] = PLANT_ROLE_LABELS.get(role, role)
    item["age_days"] = _days_between(item.get("started_on"))
    item["stage_days"] = _days_between(item.get("current_stage_started_on"))
    item["harvest_forecast"] = calculate_harvest_forecast(
        item.get("flowering_started_on"),
        item.get("expected_flower_days"),
    )
    return item


def list_plants(status=None, stage=None, cultivar_id=None, batch_id=None, search=None):
    db = _db()
    try:
        where = []
        params = []

        if status:
            where.append("p.status = ?")
            params.append(status)

        if stage:
            where.append("p.current_stage = ?")
            params.append(stage)

        if cultivar_id:
            where.append("p.cultivar_id = ?")
            params.append(int(cultivar_id))

        if batch_id:
            where.append("p.batch_id = ?")
            params.append(int(batch_id))

        if search:
            q = f"%{search.strip()}%"
            where.append(
                "(p.code LIKE ? OR p.display_name LIKE ? OR c.name LIKE ? OR b.name LIKE ? OR p.location LIKE ?)"
            )
            params.extend([q, q, q, q, q])

        sql = PLANT_SELECT
        if where:
            sql += " WHERE " + " AND ".join(where)

        sql += """
            ORDER BY
                CASE p.status WHEN 'active' THEN 0 ELSE 1 END,
                p.started_on DESC,
                p.id DESC
        """

        return [
            _decorate_plant(dict(row))
            for row in db.execute(sql, params).fetchall()
        ]
    finally:
        db.close()


def get_plant(plant_id):
    db = _db()
    try:
        row = db.execute(
            PLANT_SELECT + " WHERE p.id = ?",
            (plant_id,),
        ).fetchone()
        return _decorate_plant(dict(row)) if row else None
    finally:
        db.close()


def save_plant(data, plant_id=None, created_by=None):
    db = _db()
    try:
        now = _now()
        started_on = _iso_date(data.get("started_on"))
        stage = _text(data.get("current_stage")) or "germination"
        status = _text(data.get("status")) or "active"

        cultivar_id = _to_int(data.get("cultivar_id"))
        batch_id = _to_int(data.get("batch_id"))

        display_name = _text(data.get("display_name"))
        if not display_name:
            raise ValueError("Die Pflanzenbezeichnung darf nicht leer sein.")

        code = _text(data.get("code"))
        if not code:
            code = _next_code(db, "pm_plants", f"PL-{date.today().year}", 4)

        payload = {
            "code": code.upper(),
            "display_name": display_name,
            "cultivar_id": cultivar_id,
            "batch_id": batch_id,
            "location": _text(data.get("location")) or None,
            "started_on": started_on,
            "current_stage": stage,
            "status": status,
            "notes": _text(data.get("notes")) or None,
        }

        if plant_id:
            current = db.execute(
                "SELECT current_stage FROM pm_plants WHERE id = ?",
                (plant_id,),
            ).fetchone()
            if not current:
                raise ValueError("Pflanze wurde nicht gefunden.")

            db.execute(
                """
                UPDATE pm_plants SET
                    code=:code,
                    display_name=:display_name,
                    cultivar_id=:cultivar_id,
                    batch_id=:batch_id,
                    location=:location,
                    started_on=:started_on,
                    status=:status,
                    notes=:notes,
                    updated_at=:updated_at
                WHERE id=:id
                """,
                {**payload, "updated_at": now, "id": int(plant_id)},
            )
            saved_id = int(plant_id)

            if stage != current["current_stage"]:
                _set_stage_tx(
                    db,
                    saved_id,
                    stage,
                    started_on=date.today().isoformat(),
                    note="Phase über Pflanzenformular geändert",
                    created_by=created_by,
                )
        else:
            cur = db.execute(
                """
                INSERT INTO pm_plants (
                    code, display_name, cultivar_id, batch_id, location,
                    started_on, current_stage, status, notes,
                    created_at, updated_at
                )
                VALUES (
                    :code, :display_name, :cultivar_id, :batch_id, :location,
                    :started_on, :current_stage, :status, :notes,
                    :created_at, :updated_at
                )
                """,
                {**payload, "created_at": now, "updated_at": now},
            )
            saved_id = cur.lastrowid
            db.execute(
                """
                INSERT INTO pm_stage_events (
                    plant_id, stage, started_on, ended_on,
                    note, created_by, created_at
                )
                VALUES (?, ?, ?, NULL, ?, ?, ?)
                """,
                (
                    saved_id,
                    stage,
                    started_on,
                    "Initiale Phase",
                    created_by,
                    now,
                ),
            )

            # Ab Phase 7 wird auch die Pflanzenrolle historisiert. Der Guard
            # hält den älteren Phase-5-Datenbanktest weiterhin kompatibel.
            if _table_exists(db, "pm_plant_role_events"):
                db.execute(
                    """
                    INSERT INTO pm_plant_role_events (
                        plant_id, role, started_on, ended_on,
                        note, created_by, created_at
                    )
                    VALUES (?, 'production', ?, NULL, ?, ?, ?)
                    """,
                    (
                        saved_id,
                        started_on,
                        "Initiale Produktionsrolle",
                        created_by,
                        now,
                    ),
                )

        db.commit()
        return saved_id
    finally:
        db.close()


def _set_stage_tx(db, plant_id, stage, started_on=None, note=None, created_by=None):
    started_on = _iso_date(started_on)
    current = db.execute(
        "SELECT current_stage FROM pm_plants WHERE id = ?",
        (plant_id,),
    ).fetchone()
    if not current:
        raise ValueError("Pflanze wurde nicht gefunden.")

    if current["current_stage"] == stage:
        return False

    db.execute(
        """
        UPDATE pm_stage_events
        SET ended_on = ?
        WHERE plant_id = ? AND ended_on IS NULL
        """,
        (started_on, plant_id),
    )

    db.execute(
        """
        INSERT INTO pm_stage_events (
            plant_id, stage, started_on, ended_on,
            note, created_by, created_at
        )
        VALUES (?, ?, ?, NULL, ?, ?, ?)
        """,
        (
            plant_id,
            stage,
            started_on,
            (note or "").strip() or None,
            created_by,
            _now(),
        ),
    )

    db.execute(
        """
        UPDATE pm_plants
        SET current_stage = ?, updated_at = ?
        WHERE id = ?
        """,
        (stage, _now(), plant_id),
    )

    if stage == "finished":
        db.execute(
            """
            UPDATE pm_plants
            SET status = 'finished', updated_at = ?
            WHERE id = ?
            """,
            (_now(), plant_id),
        )
    return True


def set_plant_stage(plant_id, stage, started_on=None, note=None, created_by=None):
    db = _db()
    try:
        changed = _set_stage_tx(
            db,
            int(plant_id),
            stage,
            started_on=started_on,
            note=note,
            created_by=created_by,
        )
        db.commit()
        return changed
    finally:
        db.close()


def correct_current_stage_start(plant_id, started_on, note=None):
    """Korrigiert die Grenze der aktuell offenen Pflanzenphase.

    Die Korrektur erzeugt bewusst keine zweite Phase mit demselben Namen. Der
    offene Eintrag und das Ende seines direkten Vorgängers werden atomar auf
    dieselbe Datumsgrenze gesetzt. Dadurch bleiben Timeline und Blüteprognose
    widerspruchsfrei.
    """

    try:
        corrected_date = date.fromisoformat(str(started_on or "")[:10])
    except (TypeError, ValueError):
        raise ValueError("Bitte ein gültiges Startdatum angeben.")

    if corrected_date > date.today():
        raise ValueError("Das Startdatum einer laufenden Phase darf nicht in der Zukunft liegen.")

    db = _db()
    try:
        plant = db.execute(
            "SELECT id, current_stage, started_on FROM pm_plants WHERE id = ?",
            (int(plant_id),),
        ).fetchone()
        if not plant:
            raise ValueError("Pflanze wurde nicht gefunden.")

        current = db.execute(
            """
            SELECT *
            FROM pm_stage_events
            WHERE plant_id = ? AND ended_on IS NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (int(plant_id),),
        ).fetchone()
        if not current:
            raise ValueError("Für die aktuelle Phase fehlt ein offener Verlaufseintrag.")
        if current["stage"] != plant["current_stage"]:
            raise ValueError("Aktuelle Phase und Phasenverlauf sind nicht synchron.")

        old_date = date.fromisoformat(str(current["started_on"])[:10])
        if corrected_date == old_date:
            return None

        previous = db.execute(
            """
            SELECT *
            FROM pm_stage_events
            WHERE plant_id = ? AND id < ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (int(plant_id), int(current["id"])),
        ).fetchone()
        if previous:
            previous_start = date.fromisoformat(str(previous["started_on"])[:10])
            if corrected_date < previous_start:
                raise ValueError(
                    "Das korrigierte Startdatum darf nicht vor dem Beginn der vorherigen Phase liegen."
                )

        correction_note = (note or "").strip()
        event_note = current["note"]
        if correction_note:
            addition = f"Datumskorrektur: {correction_note}"
            event_note = f"{event_note} | {addition}" if event_note else addition

        db.execute(
            "UPDATE pm_stage_events SET started_on = ?, note = ? WHERE id = ?",
            (corrected_date.isoformat(), event_note, int(current["id"])),
        )
        if previous:
            db.execute(
                "UPDATE pm_stage_events SET ended_on = ? WHERE id = ?",
                (corrected_date.isoformat(), int(previous["id"])),
            )
        elif str(plant["started_on"] or "")[:10] == old_date.isoformat():
            db.execute(
                "UPDATE pm_plants SET started_on = ? WHERE id = ?",
                (corrected_date.isoformat(), int(plant_id)),
            )

        db.execute(
            "UPDATE pm_plants SET updated_at = ? WHERE id = ?",
            (_now(), int(plant_id)),
        )
        db.commit()
        return {
            "stage": current["stage"],
            "old_started_on": old_date.isoformat(),
            "new_started_on": corrected_date.isoformat(),
            "previous_stage": previous["stage"] if previous else None,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def set_plant_status(plant_id, status):
    db = _db()
    try:
        db.execute(
            """
            UPDATE pm_plants
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, _now(), int(plant_id)),
        )
        db.commit()
    finally:
        db.close()


def get_stage_events(plant_id):
    db = _db()
    try:
        rows = db.execute(
            """
            SELECT *
            FROM pm_stage_events
            WHERE plant_id = ?
            ORDER BY started_on ASC, id ASC
            """,
            (plant_id,),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["stage_label"] = STAGE_LABELS.get(item["stage"], item["stage"])
            item["stage_color"] = STAGE_COLORS.get(item["stage"], "#64748b")
            item["days"] = _days_between(
                item["started_on"],
                item["ended_on"] or date.today().isoformat(),
            )
            result.append(item)
        return result
    finally:
        db.close()


# ---------------------------------------------------------------------
# Dashboard / Timeline
# ---------------------------------------------------------------------

def get_dashboard():
    active = list_plants(status="active")
    cultivars = list_cultivars(include_inactive=False)
    batches = list_batches(include_archived=False)

    stage_counts = {}
    for plant in active:
        code = plant["current_stage"]
        stage_counts.setdefault(
            code,
            {
                "stage": code,
                "label": STAGE_LABELS.get(code, code),
                "color": STAGE_COLORS.get(code, "#64748b"),
                "count": 0,
            },
        )
        stage_counts[code]["count"] += 1

    return {
        "active_plants": active,
        "active_plant_count": len(active),
        "cultivar_count": len(cultivars),
        "active_batch_count": sum(1 for b in batches if b["status"] == "active"),
        "stage_counts": list(stage_counts.values()),
    }


def get_timeline(active_only=True):
    plants = list_plants(status="active" if active_only else None)
    rows = []
    all_dates = []

    for plant in plants:
        events = get_stage_events(plant["id"])
        if not events:
            continue

        forecast = plant.get("harvest_forecast")
        if forecast:
            try:
                all_dates.append(date.fromisoformat(forecast["harvest_on"]))
            except (TypeError, ValueError):
                pass

        for event in events:
            try:
                all_dates.append(date.fromisoformat(event["started_on"][:10]))
                end = event["ended_on"]
                if end:
                    all_dates.append(date.fromisoformat(end[:10]))
            except Exception:
                pass

        rows.append({
            "plant": plant,
            "events": events,
            "harvest_forecast": forecast,
        })

    if not all_dates:
        today = date.today()
        return {
            "rows": [],
            "start": today.isoformat(),
            "end": today.isoformat(),
            "start_label": today.strftime("%d.%m.%Y"),
            "end_label": today.strftime("%d.%m.%Y"),
            "total_days": 1,
            "ticks": [],
        }

    start = min(all_dates)
    end = max(max(all_dates), date.today())
    total_days = max(1, (end - start).days + 1)

    ticks = []
    cursor = start
    while cursor <= end:
        offset = (cursor - start).days
        ticks.append(
            {
                "label": cursor.strftime("%d.%m."),
                "left": round((offset / total_days) * 100, 3),
            }
        )
        cursor = cursor.fromordinal(cursor.toordinal() + 7)

    for row in rows:
        segments = []
        for event in row["events"]:
            s = date.fromisoformat(event["started_on"][:10])
            e = (
                date.fromisoformat(event["ended_on"][:10])
                if event["ended_on"]
                else date.today()
            )
            left = ((s - start).days / total_days) * 100
            width = max(1.2, ((e - s).days + 1) / total_days * 100)
            segments.append(
                {
                    **event,
                    "left": round(left, 3),
                    "width": round(width, 3),
                }
            )
        row["segments"] = segments

        forecast = row.get("harvest_forecast")
        if forecast:
            flower_start = date.fromisoformat(
                forecast["flowering_started_on"]
            )
            harvest_on = date.fromisoformat(forecast["harvest_on"])
            planned_left = ((flower_start - start).days / total_days) * 100
            planned_width = max(
                1.2,
                ((harvest_on - flower_start).days + 1)
                / total_days
                * 100,
            )
            forecast.update({
                "left": round(planned_left, 3),
                "width": round(planned_width, 3),
                "harvest_left": round(
                    ((harvest_on - start).days / total_days) * 100,
                    3,
                ),
            })

    return {
        "rows": rows,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "start_label": start.strftime("%d.%m.%Y"),
        "end_label": end.strftime("%d.%m.%Y"),
        "total_days": total_days,
        "ticks": ticks,
    }


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _truthy(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "ja", "on", "x"}


def _to_int(value):
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except Exception:
        return None
