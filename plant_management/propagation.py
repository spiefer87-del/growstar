import sqlite3
import time
from datetime import date
from pathlib import Path

from .constants import (
    PLANT_ROLE_LABELS,
    PROPAGATION_METHOD_LABELS,
    PROPAGATION_STATUS_LABELS,
    PROPAGATION_UNIT_STATUS_LABELS,
    SEED_LOT_STATUS_LABELS,
    SEED_TYPE_LABELS,
)


DB_FILE = Path(__file__).resolve().parent.parent / "data.db"


def _db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now():
    return int(time.time())


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


def _to_int(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def _ensure_column(db, table, column, definition):
    columns = {
        row["name"]
        for row in db.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        db.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def _next_code(db, table, prefix, width=4):
    row = db.execute(
        f"SELECT id FROM {table} ORDER BY id DESC LIMIT 1"
    ).fetchone()
    next_id = (row["id"] if row else 0) + 1
    return f"{prefix}-{next_id:0{width}d}"


def init_propagation_db():
    """
    Nicht-destruktive Erweiterung des Phase-5/6 Pflanzenmodells.

    Eine Mutterpflanze bleibt eine normale pm_plants-Pflanze. Ihre Rolle
    wird separat historisiert. Dadurch kann sie später wieder in die
    Produktion wechseln, blühen oder ihren Lebenszyklus beenden.
    """
    db = _db()
    try:
        _ensure_column(
            db,
            "pm_plants",
            "genetic_line_id",
            "INTEGER",
        )
        _ensure_column(
            db,
            "pm_plants",
            "current_role",
            "TEXT NOT NULL DEFAULT 'production'",
        )

        db.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_pm_plants_genetic_line
            ON pm_plants(genetic_line_id);

            CREATE INDEX IF NOT EXISTS idx_pm_plants_role
            ON pm_plants(current_role);

            CREATE TABLE IF NOT EXISTS pm_genetic_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                cultivar_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                source_plant_id INTEGER,
                selection_type TEXT,
                selected_on TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                notes TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY(cultivar_id) REFERENCES pm_cultivars(id),
                FOREIGN KEY(source_plant_id) REFERENCES pm_plants(id)
            );

            CREATE INDEX IF NOT EXISTS idx_pm_genetic_lines_cultivar
            ON pm_genetic_lines(cultivar_id);

            CREATE INDEX IF NOT EXISTS idx_pm_genetic_lines_status
            ON pm_genetic_lines(status);

            CREATE TABLE IF NOT EXISTS pm_plant_role_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plant_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                started_on TEXT NOT NULL,
                ended_on TEXT,
                note TEXT,
                created_by INTEGER,
                created_by_name TEXT,
                created_at INTEGER NOT NULL,
                FOREIGN KEY(plant_id) REFERENCES pm_plants(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_pm_plant_role_events_plant
            ON pm_plant_role_events(plant_id, started_on);

            CREATE TABLE IF NOT EXISTS pm_seed_lots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                cultivar_id INTEGER NOT NULL,
                supplier TEXT,
                breeder_lot TEXT,
                origin_type TEXT,
                acquired_on TEXT,
                produced_on TEXT,
                seed_type TEXT,
                storage_location TEXT,
                status TEXT NOT NULL DEFAULT 'available',
                notes TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY(cultivar_id) REFERENCES pm_cultivars(id)
            );

            CREATE INDEX IF NOT EXISTS idx_pm_seed_lots_cultivar
            ON pm_seed_lots(cultivar_id);

            CREATE INDEX IF NOT EXISTS idx_pm_seed_lots_status
            ON pm_seed_lots(status);

            CREATE TABLE IF NOT EXISTS pm_seed_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seed_lot_id INTEGER NOT NULL,
                occurred_on TEXT NOT NULL,
                movement_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                reference_type TEXT,
                reference_id INTEGER,
                note TEXT,
                created_by INTEGER,
                created_by_name TEXT,
                created_at INTEGER NOT NULL,
                FOREIGN KEY(seed_lot_id) REFERENCES pm_seed_lots(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_pm_seed_movements_lot
            ON pm_seed_movements(seed_lot_id, occurred_on);

            CREATE TABLE IF NOT EXISTS pm_propagation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                method TEXT NOT NULL,
                cultivar_id INTEGER NOT NULL,
                genetic_line_id INTEGER,
                seed_lot_id INTEGER,
                mother_plant_id INTEGER,
                batch_id INTEGER,
                started_on TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                target_count INTEGER NOT NULL,
                location TEXT,
                notes TEXT,
                created_by INTEGER,
                created_by_name TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY(cultivar_id) REFERENCES pm_cultivars(id),
                FOREIGN KEY(genetic_line_id) REFERENCES pm_genetic_lines(id),
                FOREIGN KEY(seed_lot_id) REFERENCES pm_seed_lots(id),
                FOREIGN KEY(mother_plant_id) REFERENCES pm_plants(id),
                FOREIGN KEY(batch_id) REFERENCES pm_batches(id)
            );

            CREATE INDEX IF NOT EXISTS idx_pm_propagation_runs_status
            ON pm_propagation_runs(status);

            CREATE INDEX IF NOT EXISTS idx_pm_propagation_runs_method
            ON pm_propagation_runs(method);

            CREATE TABLE IF NOT EXISTS pm_propagation_units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                sequence_no INTEGER NOT NULL,
                code TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                outcome_on TEXT,
                plant_id INTEGER,
                notes TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY(run_id) REFERENCES pm_propagation_runs(id) ON DELETE CASCADE,
                FOREIGN KEY(plant_id) REFERENCES pm_plants(id)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_pm_propagation_unit_seq
            ON pm_propagation_units(run_id, sequence_no);

            CREATE TABLE IF NOT EXISTS pm_plant_origins (
                plant_id INTEGER PRIMARY KEY,
                origin_type TEXT NOT NULL,
                propagation_unit_id INTEGER,
                seed_lot_id INTEGER,
                mother_plant_id INTEGER,
                genetic_line_id INTEGER,
                created_at INTEGER NOT NULL,
                FOREIGN KEY(plant_id) REFERENCES pm_plants(id) ON DELETE CASCADE,
                FOREIGN KEY(propagation_unit_id) REFERENCES pm_propagation_units(id),
                FOREIGN KEY(seed_lot_id) REFERENCES pm_seed_lots(id),
                FOREIGN KEY(mother_plant_id) REFERENCES pm_plants(id),
                FOREIGN KEY(genetic_line_id) REFERENCES pm_genetic_lines(id)
            );
            """
        )

        db.execute(
            """
            UPDATE pm_plants
            SET current_role = 'production'
            WHERE current_role IS NULL OR TRIM(current_role) = ''
            """
        )

        # Bestehende Pflanzen erhalten genau einen initialen Rollen-Eintrag.
        db.execute(
            """
            INSERT INTO pm_plant_role_events (
                plant_id, role, started_on, ended_on,
                note, created_at
            )
            SELECT
                p.id,
                COALESCE(NULLIF(p.current_role, ''), 'production'),
                p.started_on,
                NULL,
                'Initiale Rolle beim Upgrade auf Phase 7',
                ?
            FROM pm_plants p
            WHERE NOT EXISTS (
                SELECT 1
                FROM pm_plant_role_events r
                WHERE r.plant_id = p.id
            )
            """,
            (_now(),),
        )

        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------
# Genetische Linien / Selektionen
# ---------------------------------------------------------------------

def list_genetic_lines(include_inactive=True, search=None):
    db = _db()
    try:
        where = []
        params = []

        if not include_inactive:
            where.append("g.status = 'active'")

        if search:
            q = f"%{_text(search)}%"
            where.append(
                "(g.code LIKE ? OR g.name LIKE ? OR c.name LIKE ? OR g.notes LIKE ?)"
            )
            params.extend([q, q, q, q])

        sql = """
            SELECT
                g.*,
                c.code AS cultivar_code,
                c.name AS cultivar_name,
                p.code AS source_plant_code,
                p.display_name AS source_plant_name,
                (
                    SELECT COUNT(*)
                    FROM pm_plants p2
                    WHERE p2.genetic_line_id = g.id
                ) AS plant_count,
                (
                    SELECT COUNT(*)
                    FROM pm_plants p3
                    WHERE p3.genetic_line_id = g.id
                      AND p3.status = 'active'
                      AND p3.current_role = 'mother'
                ) AS active_mother_count
            FROM pm_genetic_lines g
            JOIN pm_cultivars c ON c.id = g.cultivar_id
            LEFT JOIN pm_plants p ON p.id = g.source_plant_id
        """

        if where:
            sql += " WHERE " + " AND ".join(where)

        sql += " ORDER BY g.status = 'active' DESC, c.name, g.name"

        return [dict(row) for row in db.execute(sql, params).fetchall()]
    finally:
        db.close()


def get_genetic_line(line_id):
    db = _db()
    try:
        row = db.execute(
            """
            SELECT
                g.*,
                c.code AS cultivar_code,
                c.name AS cultivar_name,
                p.code AS source_plant_code,
                p.display_name AS source_plant_name
            FROM pm_genetic_lines g
            JOIN pm_cultivars c ON c.id = g.cultivar_id
            LEFT JOIN pm_plants p ON p.id = g.source_plant_id
            WHERE g.id = ?
            """,
            (int(line_id),),
        ).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def save_genetic_line(data, line_id=None):
    db = _db()
    try:
        now = _now()

        source_plant_id = _to_int(data.get("source_plant_id"))
        cultivar_id = _to_int(data.get("cultivar_id"))

        if source_plant_id:
            source = db.execute(
                """
                SELECT id, cultivar_id
                FROM pm_plants
                WHERE id = ?
                """,
                (source_plant_id,),
            ).fetchone()
            if not source:
                raise ValueError("Ausgangspflanze wurde nicht gefunden.")
            if not cultivar_id:
                cultivar_id = source["cultivar_id"]

        if not cultivar_id:
            raise ValueError("Bitte eine Sorte zuordnen.")

        name = _text(data.get("name"))
        if not name:
            raise ValueError("Die Bezeichnung der genetischen Linie fehlt.")

        code = _text(data.get("code"))
        if not code:
            code = _next_code(db, "pm_genetic_lines", "GEN")

        payload = {
            "code": code.upper(),
            "cultivar_id": cultivar_id,
            "name": name,
            "source_plant_id": source_plant_id,
            "selection_type": _text(data.get("selection_type")) or None,
            "selected_on": _iso_date(data.get("selected_on")),
            "status": _text(data.get("status")) or "active",
            "notes": _text(data.get("notes")) or None,
        }

        if line_id:
            db.execute(
                """
                UPDATE pm_genetic_lines SET
                    code=:code,
                    cultivar_id=:cultivar_id,
                    name=:name,
                    source_plant_id=:source_plant_id,
                    selection_type=:selection_type,
                    selected_on=:selected_on,
                    status=:status,
                    notes=:notes,
                    updated_at=:updated_at
                WHERE id=:id
                """,
                {
                    **payload,
                    "updated_at": now,
                    "id": int(line_id),
                },
            )
            saved_id = int(line_id)
        else:
            cur = db.execute(
                """
                INSERT INTO pm_genetic_lines (
                    code, cultivar_id, name, source_plant_id,
                    selection_type, selected_on, status, notes,
                    created_at, updated_at
                )
                VALUES (
                    :code, :cultivar_id, :name, :source_plant_id,
                    :selection_type, :selected_on, :status, :notes,
                    :created_at, :updated_at
                )
                """,
                {
                    **payload,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            saved_id = int(cur.lastrowid)

            if source_plant_id:
                db.execute(
                    """
                    UPDATE pm_plants
                    SET genetic_line_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (saved_id, now, source_plant_id),
                )

        db.commit()
        return saved_id
    finally:
        db.close()


def genetic_line_plants(line_id):
    db = _db()
    try:
        return [
            dict(row)
            for row in db.execute(
                """
                SELECT p.*
                FROM pm_plants p
                WHERE p.genetic_line_id = ?
                ORDER BY
                    CASE p.status WHEN 'active' THEN 0 ELSE 1 END,
                    p.display_name
                """,
                (int(line_id),),
            ).fetchall()
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------
# Pflanzenrollen / Mutterpflanzen
# ---------------------------------------------------------------------

def set_plant_role(
    plant_id,
    role,
    *,
    started_on=None,
    genetic_line_id=None,
    note=None,
    user_id=None,
    user_name=None,
):
    if role not in PLANT_ROLE_LABELS:
        raise ValueError("Ungültige Pflanzenrolle.")

    db = _db()
    try:
        plant = db.execute(
            """
            SELECT id, current_role, genetic_line_id, status
            FROM pm_plants
            WHERE id = ?
            """,
            (int(plant_id),),
        ).fetchone()

        if not plant:
            raise ValueError("Pflanze wurde nicht gefunden.")

        started_on = _iso_date(started_on)

        if role in {"mother", "donor"}:
            resolved_line_id = (
                int(genetic_line_id)
                if genetic_line_id
                else plant["genetic_line_id"]
            )
            if not resolved_line_id:
                raise ValueError(
                    "Mutter-/Spenderpflanzen benötigen eine genetische Linie."
                )

            line = db.execute(
                "SELECT id FROM pm_genetic_lines WHERE id = ?",
                (resolved_line_id,),
            ).fetchone()
            if not line:
                raise ValueError("Genetische Linie wurde nicht gefunden.")
        else:
            resolved_line_id = (
                int(genetic_line_id)
                if genetic_line_id
                else plant["genetic_line_id"]
            )

        if plant["current_role"] == role and (
            not genetic_line_id
            or resolved_line_id == plant["genetic_line_id"]
        ):
            return False

        db.execute(
            """
            UPDATE pm_plant_role_events
            SET ended_on = ?
            WHERE plant_id = ? AND ended_on IS NULL
            """,
            (started_on, int(plant_id)),
        )

        db.execute(
            """
            INSERT INTO pm_plant_role_events (
                plant_id, role, started_on, ended_on,
                note, created_by, created_by_name, created_at
            )
            VALUES (?, ?, ?, NULL, ?, ?, ?, ?)
            """,
            (
                int(plant_id),
                role,
                started_on,
                _text(note) or None,
                user_id,
                user_name,
                _now(),
            ),
        )

        db.execute(
            """
            UPDATE pm_plants
            SET current_role = ?,
                genetic_line_id = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                role,
                resolved_line_id,
                _now(),
                int(plant_id),
            ),
        )

        db.commit()
        return True
    finally:
        db.close()


def get_role_events(plant_id):
    db = _db()
    try:
        rows = db.execute(
            """
            SELECT *
            FROM pm_plant_role_events
            WHERE plant_id = ?
            ORDER BY started_on ASC, id ASC
            """,
            (int(plant_id),),
        ).fetchall()

        result = []
        for row in rows:
            item = dict(row)
            item["role_label"] = PLANT_ROLE_LABELS.get(
                item["role"],
                item["role"],
            )
            result.append(item)
        return result
    finally:
        db.close()


def list_mother_plants(active_only=True):
    db = _db()
    try:
        sql = """
            SELECT
                p.*,
                c.name AS cultivar_name,
                c.code AS cultivar_code,
                g.name AS genetic_line_name,
                g.code AS genetic_line_code,
                (
                    SELECT COUNT(*)
                    FROM pm_propagation_runs r
                    WHERE r.mother_plant_id = p.id
                ) AS propagation_run_count,
                (
                    SELECT COUNT(*)
                    FROM pm_propagation_units u
                    JOIN pm_propagation_runs r ON r.id = u.run_id
                    WHERE r.mother_plant_id = p.id
                      AND u.plant_id IS NOT NULL
                ) AS descendant_count
            FROM pm_plants p
            LEFT JOIN pm_cultivars c ON c.id = p.cultivar_id
            LEFT JOIN pm_genetic_lines g ON g.id = p.genetic_line_id
            WHERE p.current_role IN ('mother', 'donor')
        """
        params = []

        if active_only:
            sql += " AND p.status = 'active'"

        sql += " ORDER BY c.name, p.display_name"

        rows = []
        for row in db.execute(sql, params).fetchall():
            item = dict(row)
            item["role_label"] = PLANT_ROLE_LABELS.get(
                item["current_role"],
                item["current_role"],
            )
            rows.append(item)
        return rows
    finally:
        db.close()


def get_mother_summary(plant_id):
    db = _db()
    try:
        row = db.execute(
            """
            SELECT
                COUNT(DISTINCT r.id) AS run_count,
                COUNT(u.id) AS unit_count,
                SUM(
                    CASE
                        WHEN u.status IN ('rooted', 'plant_created')
                        THEN 1 ELSE 0
                    END
                ) AS successful_units,
                SUM(
                    CASE
                        WHEN u.status = 'failed'
                        THEN 1 ELSE 0
                    END
                ) AS failed_units,
                SUM(
                    CASE
                        WHEN u.plant_id IS NOT NULL
                        THEN 1 ELSE 0
                    END
                ) AS created_plants
            FROM pm_propagation_runs r
            LEFT JOIN pm_propagation_units u ON u.run_id = r.id
            WHERE r.mother_plant_id = ?
            """,
            (int(plant_id),),
        ).fetchone()

        total = int(row["unit_count"] or 0)
        successful = int(row["successful_units"] or 0)
        failed = int(row["failed_units"] or 0)
        decided = successful + failed
        return {
            "run_count": int(row["run_count"] or 0),
            "unit_count": total,
            "successful_units": successful,
            "failed_units": failed,
            "created_plants": int(row["created_plants"] or 0),
            "success_rate": (
                round(successful / decided * 100, 1)
                if decided
                else None
            ),
        }
    finally:
        db.close()


# ---------------------------------------------------------------------
# Saatgut-Lots / Lagerbewegungen
# ---------------------------------------------------------------------

def _seed_stock_tx(db, lot_id):
    row = db.execute(
        """
        SELECT COALESCE(SUM(quantity), 0) AS stock
        FROM pm_seed_movements
        WHERE seed_lot_id = ?
        """,
        (int(lot_id),),
    ).fetchone()
    return int(row["stock"] or 0)


def seed_stock(lot_id):
    db = _db()
    try:
        return _seed_stock_tx(db, lot_id)
    finally:
        db.close()


def _seed_lot_stats_tx(db, lot_id):
    row = db.execute(
        """
        SELECT
            COUNT(u.id) AS total_units,
            SUM(
                CASE
                    WHEN u.status IN ('germinated', 'plant_created')
                    THEN 1 ELSE 0
                END
            ) AS successful_units,
            SUM(
                CASE
                    WHEN u.status = 'failed'
                    THEN 1 ELSE 0
                END
            ) AS failed_units
        FROM pm_propagation_runs r
        LEFT JOIN pm_propagation_units u ON u.run_id = r.id
        WHERE r.seed_lot_id = ?
        """,
        (int(lot_id),),
    ).fetchone()

    total = int(row["total_units"] or 0)
    successful = int(row["successful_units"] or 0)
    failed = int(row["failed_units"] or 0)
    decided = successful + failed

    return {
        "used_units": total,
        "successful_units": successful,
        "failed_units": failed,
        "success_rate": (
            round(successful / decided * 100, 1)
            if decided
            else None
        ),
    }


def list_seed_lots(include_empty=True, include_archived=True, search=None):
    db = _db()
    try:
        where = []
        params = []

        if not include_archived:
            where.append("s.status != 'archived'")

        if search:
            q = f"%{_text(search)}%"
            where.append(
                "(s.code LIKE ? OR c.name LIKE ? OR s.breeder_lot LIKE ? "
                "OR s.supplier LIKE ? OR s.storage_location LIKE ?)"
            )
            params.extend([q, q, q, q, q])

        sql = """
            SELECT
                s.*,
                c.code AS cultivar_code,
                c.name AS cultivar_name,
                COALESCE((
                    SELECT SUM(m.quantity)
                    FROM pm_seed_movements m
                    WHERE m.seed_lot_id = s.id
                ), 0) AS stock
            FROM pm_seed_lots s
            JOIN pm_cultivars c ON c.id = s.cultivar_id
        """

        if where:
            sql += " WHERE " + " AND ".join(where)

        if not include_empty:
            if where:
                sql += " AND "
            else:
                sql += " WHERE "
            sql += """
                COALESCE((
                    SELECT SUM(m2.quantity)
                    FROM pm_seed_movements m2
                    WHERE m2.seed_lot_id = s.id
                ), 0) > 0
            """

        sql += " ORDER BY s.status = 'available' DESC, c.name, s.acquired_on DESC"

        rows = []
        for row in db.execute(sql, params).fetchall():
            item = dict(row)
            item["status_label"] = SEED_LOT_STATUS_LABELS.get(
                item["status"], item["status"]
            )
            item["seed_type_label"] = SEED_TYPE_LABELS.get(
                item.get("seed_type"), item.get("seed_type") or "—"
            )
            stats = _seed_lot_stats_tx(db, item["id"])
            item.update(stats)
            rows.append(item)
        return rows
    finally:
        db.close()


def get_seed_lot(lot_id):
    db = _db()
    try:
        row = db.execute(
            """
            SELECT
                s.*,
                c.code AS cultivar_code,
                c.name AS cultivar_name
            FROM pm_seed_lots s
            JOIN pm_cultivars c ON c.id = s.cultivar_id
            WHERE s.id = ?
            """,
            (int(lot_id),),
        ).fetchone()

        if not row:
            return None

        item = dict(row)
        item["stock"] = _seed_stock_tx(db, lot_id)
        item["status_label"] = SEED_LOT_STATUS_LABELS.get(
            item["status"], item["status"]
        )
        item["seed_type_label"] = SEED_TYPE_LABELS.get(
            item.get("seed_type"), item.get("seed_type") or "—"
        )
        item.update(_seed_lot_stats_tx(db, lot_id))
        return item
    finally:
        db.close()


def get_seed_lot_by_code(code):
    db = _db()
    try:
        row = db.execute(
            "SELECT id FROM pm_seed_lots WHERE code = ? COLLATE NOCASE",
            (_text(code),),
        ).fetchone()
        return get_seed_lot(row["id"]) if row else None
    finally:
        db.close()


def _book_seed_movement_tx(
    db,
    lot_id,
    quantity,
    movement_type,
    *,
    occurred_on=None,
    reference_type=None,
    reference_id=None,
    note=None,
    user_id=None,
    user_name=None,
):
    quantity = int(quantity)

    if quantity == 0:
        raise ValueError("Die Bestandsbewegung darf nicht 0 sein.")

    current_stock = _seed_stock_tx(db, lot_id)
    new_stock = current_stock + quantity

    if new_stock < 0:
        raise ValueError(
            f"Nicht genügend Saatgut verfügbar. Bestand: {current_stock}."
        )

    lot_status = db.execute(
        "SELECT status FROM pm_seed_lots WHERE id = ?",
        (int(lot_id),),
    ).fetchone()
    if not lot_status:
        raise ValueError("Saatgut-Lot wurde nicht gefunden.")

    if new_stock == 0 and lot_status["status"] == "available":
        db.execute(
            "UPDATE pm_seed_lots SET status='depleted', updated_at=? WHERE id=?",
            (_now(), int(lot_id)),
        )
    elif new_stock > 0 and lot_status["status"] == "depleted":
        db.execute(
            "UPDATE pm_seed_lots SET status='available', updated_at=? WHERE id=?",
            (_now(), int(lot_id)),
        )

    db.execute(
        """
        INSERT INTO pm_seed_movements (
            seed_lot_id, occurred_on, movement_type, quantity,
            reference_type, reference_id, note,
            created_by, created_by_name, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(lot_id),
            _iso_date(occurred_on),
            _text(movement_type) or "adjustment",
            quantity,
            _text(reference_type) or None,
            reference_id,
            _text(note) or None,
            user_id,
            user_name,
            _now(),
        ),
    )
    return new_stock


def book_seed_movement(
    lot_id,
    quantity,
    movement_type,
    *,
    occurred_on=None,
    reference_type=None,
    reference_id=None,
    note=None,
    user_id=None,
    user_name=None,
):
    db = _db()
    try:
        new_stock = _book_seed_movement_tx(
            db,
            lot_id,
            quantity,
            movement_type,
            occurred_on=occurred_on,
            reference_type=reference_type,
            reference_id=reference_id,
            note=note,
            user_id=user_id,
            user_name=user_name,
        )
        db.commit()
        return new_stock
    finally:
        db.close()


def list_seed_movements(lot_id):
    db = _db()
    try:
        return [
            dict(row)
            for row in db.execute(
                """
                SELECT *
                FROM pm_seed_movements
                WHERE seed_lot_id = ?
                ORDER BY occurred_on DESC, id DESC
                """,
                (int(lot_id),),
            ).fetchall()
        ]
    finally:
        db.close()


def save_seed_lot(
    data,
    lot_id=None,
    *,
    initial_quantity=None,
    user_id=None,
    user_name=None,
):
    db = _db()
    try:
        cultivar_id = _to_int(data.get("cultivar_id"))
        if not cultivar_id:
            raise ValueError("Bitte eine Sorte auswählen.")

        cultivar = db.execute(
            "SELECT id FROM pm_cultivars WHERE id = ?",
            (cultivar_id,),
        ).fetchone()
        if not cultivar:
            raise ValueError("Sorte wurde nicht gefunden.")

        code = _text(data.get("code"))
        if not code:
            code = _next_code(
                db,
                "pm_seed_lots",
                f"SEED-{date.today().year}",
                3,
            )

        payload = {
            "code": code.upper(),
            "cultivar_id": cultivar_id,
            "supplier": _text(data.get("supplier")) or None,
            "breeder_lot": _text(data.get("breeder_lot")) or None,
            "origin_type": _text(data.get("origin_type")) or None,
            "acquired_on": _iso_date(data.get("acquired_on")),
            "produced_on": (
                _iso_date(data.get("produced_on"))
                if data.get("produced_on")
                else None
            ),
            "seed_type": _text(data.get("seed_type")) or None,
            "storage_location": _text(data.get("storage_location")) or None,
            "status": _text(data.get("status")) or "available",
            "notes": _text(data.get("notes")) or None,
        }

        now = _now()

        if lot_id:
            db.execute(
                """
                UPDATE pm_seed_lots SET
                    code=:code,
                    cultivar_id=:cultivar_id,
                    supplier=:supplier,
                    breeder_lot=:breeder_lot,
                    origin_type=:origin_type,
                    acquired_on=:acquired_on,
                    produced_on=:produced_on,
                    seed_type=:seed_type,
                    storage_location=:storage_location,
                    status=:status,
                    notes=:notes,
                    updated_at=:updated_at
                WHERE id=:id
                """,
                {
                    **payload,
                    "updated_at": now,
                    "id": int(lot_id),
                },
            )
            saved_id = int(lot_id)
        else:
            cur = db.execute(
                """
                INSERT INTO pm_seed_lots (
                    code, cultivar_id, supplier, breeder_lot,
                    origin_type, acquired_on, produced_on,
                    seed_type, storage_location, status, notes,
                    created_at, updated_at
                )
                VALUES (
                    :code, :cultivar_id, :supplier, :breeder_lot,
                    :origin_type, :acquired_on, :produced_on,
                    :seed_type, :storage_location, :status, :notes,
                    :created_at, :updated_at
                )
                """,
                {
                    **payload,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            saved_id = int(cur.lastrowid)

            initial_quantity = _to_int(initial_quantity)
            if initial_quantity:
                if initial_quantity < 0:
                    raise ValueError("Anfangsbestand darf nicht negativ sein.")
                _book_seed_movement_tx(
                    db,
                    saved_id,
                    initial_quantity,
                    "receipt",
                    occurred_on=payload["acquired_on"],
                    note="Anfangsbestand",
                    user_id=user_id,
                    user_name=user_name,
                )

        db.commit()
        return saved_id
    finally:
        db.close()


# ---------------------------------------------------------------------
# Vermehrungsansätze
# ---------------------------------------------------------------------

def _unit_initial_status(method):
    return "germinating" if method == "seed" else "rooting"


def _unit_success_status(method):
    return "germinated" if method == "seed" else "rooted"


def _allowed_unit_statuses(method):
    if method == "seed":
        return {
            "germinating",
            "germinated",
            "failed",
            "plant_created",
        }
    if method == "cutting":
        return {
            "rooting",
            "rooted",
            "failed",
            "plant_created",
        }
    return {
        "started",
        "successful",
        "failed",
        "plant_created",
    }


def create_propagation_run(
    data,
    *,
    user_id=None,
    user_name=None,
):
    method = _text(data.get("method"))
    if method not in PROPAGATION_METHOD_LABELS:
        raise ValueError("Ungültige Vermehrungsmethode.")

    target_count = _to_int(data.get("target_count"))
    if not target_count or target_count < 1 or target_count > 500:
        raise ValueError("Bitte eine Anzahl zwischen 1 und 500 angeben.")

    db = _db()
    try:
        seed_lot_id = _to_int(data.get("seed_lot_id"))
        mother_plant_id = _to_int(data.get("mother_plant_id"))
        batch_id = _to_int(data.get("batch_id"))

        cultivar_id = None
        genetic_line_id = None

        if method == "seed":
            if not seed_lot_id:
                raise ValueError("Für einen Samenansatz ist ein Saatgut-Lot erforderlich.")

            lot = db.execute(
                """
                SELECT *
                FROM pm_seed_lots
                WHERE id = ?
                """,
                (seed_lot_id,),
            ).fetchone()

            if not lot:
                raise ValueError("Saatgut-Lot wurde nicht gefunden.")

            if lot["status"] != "available":
                raise ValueError("Dieses Saatgut-Lot ist nicht für Entnahmen freigegeben.")

            cultivar_id = lot["cultivar_id"]

            if _seed_stock_tx(db, seed_lot_id) < target_count:
                raise ValueError(
                    f"Nicht genügend Saatgut vorhanden. Bestand: "
                    f"{_seed_stock_tx(db, seed_lot_id)}."
                )

        elif method == "cutting":
            if not mother_plant_id:
                raise ValueError("Für Stecklinge ist eine Mutter-/Spenderpflanze erforderlich.")

            mother = db.execute(
                """
                SELECT *
                FROM pm_plants
                WHERE id = ?
                """,
                (mother_plant_id,),
            ).fetchone()

            if not mother:
                raise ValueError("Mutterpflanze wurde nicht gefunden.")

            if mother["status"] != "active":
                raise ValueError("Die Mutter-/Spenderpflanze ist nicht aktiv.")

            if mother["current_role"] not in {"mother", "donor"}:
                raise ValueError(
                    "Stecklinge können nur einer aktiven Mutter-/Spenderpflanze "
                    "zugeordnet werden."
                )

            if not mother["genetic_line_id"]:
                raise ValueError(
                    "Die Mutterpflanze benötigt zuerst eine genetische Linie."
                )

            cultivar_id = mother["cultivar_id"]
            genetic_line_id = mother["genetic_line_id"]

        if not cultivar_id:
            raise ValueError("Für den Ansatz konnte keine Sorte bestimmt werden.")

        code = _text(data.get("code"))
        if not code:
            code = _next_code(
                db,
                "pm_propagation_runs",
                f"PROP-{date.today().year}",
                3,
            )

        name = _text(data.get("name"))
        if not name:
            name = (
                f"Samenansatz {code}"
                if method == "seed"
                else f"Stecklingsansatz {code}"
            )

        now = _now()
        started_on = _iso_date(data.get("started_on"))

        cur = db.execute(
            """
            INSERT INTO pm_propagation_runs (
                code, name, method, cultivar_id, genetic_line_id,
                seed_lot_id, mother_plant_id, batch_id,
                started_on, status, target_count, location, notes,
                created_by, created_by_name, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                code.upper(),
                name,
                method,
                cultivar_id,
                genetic_line_id,
                seed_lot_id,
                mother_plant_id,
                batch_id,
                started_on,
                target_count,
                _text(data.get("location")) or None,
                _text(data.get("notes")) or None,
                user_id,
                user_name,
                now,
                now,
            ),
        )
        run_id = int(cur.lastrowid)

        initial_status = _unit_initial_status(method)

        for sequence_no in range(1, target_count + 1):
            unit_code = f"{code.upper()}-U{sequence_no:03d}"
            db.execute(
                """
                INSERT INTO pm_propagation_units (
                    run_id, sequence_no, code, status,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    sequence_no,
                    unit_code,
                    initial_status,
                    now,
                    now,
                ),
            )

        if method == "seed":
            _book_seed_movement_tx(
                db,
                seed_lot_id,
                -target_count,
                "propagation_issue",
                occurred_on=started_on,
                reference_type="propagation_run",
                reference_id=run_id,
                note=f"Entnahme für {code.upper()}",
                user_id=user_id,
                user_name=user_name,
            )

        db.commit()
        return run_id
    finally:
        db.close()


def _decorate_run(db, item):
    item = dict(item)
    item["method_label"] = PROPAGATION_METHOD_LABELS.get(
        item["method"],
        item["method"],
    )
    item["status_label"] = PROPAGATION_STATUS_LABELS.get(
        item["status"],
        item["status"],
    )

    stats = db.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(
                CASE
                    WHEN status IN ('germinated', 'rooted', 'successful', 'plant_created')
                    THEN 1 ELSE 0
                END
            ) AS successful,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
            SUM(CASE WHEN plant_id IS NOT NULL THEN 1 ELSE 0 END) AS created
        FROM pm_propagation_units
        WHERE run_id = ?
        """,
        (item["id"],),
    ).fetchone()

    item["total_units"] = int(stats["total"] or 0)
    item["successful_units"] = int(stats["successful"] or 0)
    item["failed_units"] = int(stats["failed"] or 0)
    item["created_plants"] = int(stats["created"] or 0)
    decided = item["successful_units"] + item["failed_units"]
    item["success_rate"] = (
        round(item["successful_units"] / decided * 100, 1)
        if decided
        else None
    )
    return item


def list_propagation_runs(method=None, status=None, limit=250):
    db = _db()
    try:
        where = []
        params = []

        if method:
            where.append("r.method = ?")
            params.append(method)

        if status:
            where.append("r.status = ?")
            params.append(status)

        sql = """
            SELECT
                r.*,
                c.name AS cultivar_name,
                c.code AS cultivar_code,
                g.name AS genetic_line_name,
                g.code AS genetic_line_code,
                s.code AS seed_lot_code,
                p.code AS mother_plant_code,
                p.display_name AS mother_plant_name,
                b.code AS batch_code,
                b.name AS batch_name
            FROM pm_propagation_runs r
            JOIN pm_cultivars c ON c.id = r.cultivar_id
            LEFT JOIN pm_genetic_lines g ON g.id = r.genetic_line_id
            LEFT JOIN pm_seed_lots s ON s.id = r.seed_lot_id
            LEFT JOIN pm_plants p ON p.id = r.mother_plant_id
            LEFT JOIN pm_batches b ON b.id = r.batch_id
        """

        if where:
            sql += " WHERE " + " AND ".join(where)

        sql += " ORDER BY r.started_on DESC, r.id DESC LIMIT ?"
        params.append(max(1, min(int(limit), 1000)))

        return [
            _decorate_run(db, row)
            for row in db.execute(sql, params).fetchall()
        ]
    finally:
        db.close()


def get_propagation_run(run_id):
    db = _db()
    try:
        row = db.execute(
            """
            SELECT
                r.*,
                c.name AS cultivar_name,
                c.code AS cultivar_code,
                g.name AS genetic_line_name,
                g.code AS genetic_line_code,
                s.code AS seed_lot_code,
                p.code AS mother_plant_code,
                p.display_name AS mother_plant_name,
                b.code AS batch_code,
                b.name AS batch_name
            FROM pm_propagation_runs r
            JOIN pm_cultivars c ON c.id = r.cultivar_id
            LEFT JOIN pm_genetic_lines g ON g.id = r.genetic_line_id
            LEFT JOIN pm_seed_lots s ON s.id = r.seed_lot_id
            LEFT JOIN pm_plants p ON p.id = r.mother_plant_id
            LEFT JOIN pm_batches b ON b.id = r.batch_id
            WHERE r.id = ?
            """,
            (int(run_id),),
        ).fetchone()

        if not row:
            return None

        item = _decorate_run(db, row)
        units = []

        for unit in db.execute(
            """
            SELECT
                u.*,
                p.code AS plant_code,
                p.display_name AS plant_name
            FROM pm_propagation_units u
            LEFT JOIN pm_plants p ON p.id = u.plant_id
            WHERE u.run_id = ?
            ORDER BY u.sequence_no
            """,
            (int(run_id),),
        ).fetchall():
            unit_item = dict(unit)
            unit_item["status_label"] = PROPAGATION_UNIT_STATUS_LABELS.get(
                unit_item["status"],
                unit_item["status"],
            )
            unit_item["can_create_plant"] = (
                unit_item["status"] == _unit_success_status(item["method"])
                and not unit_item["plant_id"]
            )
            units.append(unit_item)

        item["units"] = units
        return item
    finally:
        db.close()


def update_propagation_unit(
    unit_id,
    *,
    status,
    outcome_on=None,
    notes=None,
):
    db = _db()
    try:
        row = db.execute(
            """
            SELECT u.*, r.method, r.id AS run_id
            FROM pm_propagation_units u
            JOIN pm_propagation_runs r ON r.id = u.run_id
            WHERE u.id = ?
            """,
            (int(unit_id),),
        ).fetchone()

        if not row:
            raise ValueError("Vermehrungseinheit wurde nicht gefunden.")

        if row["plant_id"]:
            raise ValueError(
                "Für diese Einheit wurde bereits eine Pflanze erzeugt."
            )

        if status not in _allowed_unit_statuses(row["method"]):
            raise ValueError("Ungültiger Status für diese Vermehrungsmethode.")

        db.execute(
            """
            UPDATE pm_propagation_units
            SET status = ?,
                outcome_on = ?,
                notes = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                _iso_date(outcome_on) if outcome_on else None,
                _text(notes) or None,
                _now(),
                int(unit_id),
            ),
        )

        _refresh_run_status_tx(db, row["run_id"])
        db.commit()
        return True
    finally:
        db.close()


def _refresh_run_status_tx(db, run_id):
    row = db.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(
                CASE
                    WHEN status IN ('failed', 'plant_created')
                    THEN 1 ELSE 0
                END
            ) AS terminal
        FROM pm_propagation_units
        WHERE run_id = ?
        """,
        (int(run_id),),
    ).fetchone()

    total = int(row["total"] or 0)
    terminal = int(row["terminal"] or 0)

    status = "completed" if total and terminal == total else "active"

    db.execute(
        """
        UPDATE pm_propagation_runs
        SET status = ?, updated_at = ?
        WHERE id = ? AND status != 'cancelled'
        """,
        (status, _now(), int(run_id)),
    )


def create_plant_from_propagation_unit(
    unit_id,
    *,
    display_name=None,
    location=None,
    user_id=None,
    user_name=None,
):
    db = _db()
    try:
        row = db.execute(
            """
            SELECT
                u.*,
                r.method,
                r.cultivar_id,
                r.genetic_line_id,
                r.seed_lot_id,
                r.mother_plant_id,
                r.batch_id,
                r.started_on,
                r.location AS run_location,
                r.code AS run_code
            FROM pm_propagation_units u
            JOIN pm_propagation_runs r ON r.id = u.run_id
            WHERE u.id = ?
            """,
            (int(unit_id),),
        ).fetchone()

        if not row:
            raise ValueError("Vermehrungseinheit wurde nicht gefunden.")

        if row["plant_id"]:
            return int(row["plant_id"])

        required_status = _unit_success_status(row["method"])
        if row["status"] != required_status:
            raise ValueError(
                f"Eine Pflanze kann erst aus dem Status "
                f"'{PROPAGATION_UNIT_STATUS_LABELS.get(required_status, required_status)}' "
                "erzeugt werden."
            )

        plant_code = _next_code(
            db,
            "pm_plants",
            f"PL-{date.today().year}",
            4,
        )

        display_name = _text(display_name) or row["code"]
        started_on = row["outcome_on"] or row["started_on"]
        stage = "seedling" if row["method"] == "seed" else "vegetative"
        genetic_line_id = (
            row["genetic_line_id"]
            if row["method"] == "cutting"
            else None
        )

        now = _now()

        cur = db.execute(
            """
            INSERT INTO pm_plants (
                code, display_name, cultivar_id, batch_id,
                location, started_on, current_stage, status,
                notes, created_at, updated_at,
                genetic_line_id, current_role
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, 'production')
            """,
            (
                plant_code,
                display_name,
                row["cultivar_id"],
                row["batch_id"],
                _text(location) or row["run_location"],
                started_on,
                stage,
                f"Automatisch aus {row['code']} erzeugt",
                now,
                now,
                genetic_line_id,
            ),
        )
        plant_id = int(cur.lastrowid)

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
                f"Erzeugt aus Vermehrungsansatz {row['run_code']}",
                user_id,
                now,
            ),
        )

        db.execute(
            """
            INSERT INTO pm_plant_role_events (
                plant_id, role, started_on, ended_on,
                note, created_by, created_by_name, created_at
            )
            VALUES (?, 'production', ?, NULL, ?, ?, ?, ?)
            """,
            (
                plant_id,
                started_on,
                f"Erzeugt aus Vermehrungsansatz {row['run_code']}",
                user_id,
                user_name,
                now,
            ),
        )

        db.execute(
            """
            INSERT INTO pm_plant_origins (
                plant_id, origin_type, propagation_unit_id,
                seed_lot_id, mother_plant_id, genetic_line_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plant_id,
                row["method"],
                int(unit_id),
                row["seed_lot_id"],
                row["mother_plant_id"],
                genetic_line_id,
                now,
            ),
        )

        db.execute(
            """
            UPDATE pm_propagation_units
            SET status = 'plant_created',
                plant_id = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (plant_id, now, int(unit_id)),
        )

        _refresh_run_status_tx(db, row["run_id"])
        db.commit()
        return plant_id
    finally:
        db.close()


def get_plant_origin(plant_id):
    db = _db()
    try:
        row = db.execute(
            """
            SELECT
                o.*,
                u.code AS propagation_unit_code,
                r.id AS propagation_run_id,
                r.code AS propagation_run_code,
                r.name AS propagation_run_name,
                s.code AS seed_lot_code,
                m.code AS mother_plant_code,
                m.display_name AS mother_plant_name,
                g.code AS genetic_line_code,
                g.name AS genetic_line_name
            FROM pm_plant_origins o
            LEFT JOIN pm_propagation_units u ON u.id = o.propagation_unit_id
            LEFT JOIN pm_propagation_runs r ON r.id = u.run_id
            LEFT JOIN pm_seed_lots s ON s.id = o.seed_lot_id
            LEFT JOIN pm_plants m ON m.id = o.mother_plant_id
            LEFT JOIN pm_genetic_lines g ON g.id = o.genetic_line_id
            WHERE o.plant_id = ?
            """,
            (int(plant_id),),
        ).fetchone()

        if not row:
            return None

        item = dict(row)
        item["origin_label"] = (
            "Samen"
            if item["origin_type"] == "seed"
            else "Steckling"
            if item["origin_type"] == "cutting"
            else item["origin_type"]
        )
        return item
    finally:
        db.close()


# ---------------------------------------------------------------------
# Dashboard / Kennzahlen
# ---------------------------------------------------------------------

def propagation_dashboard():
    db = _db()
    try:
        seed_row = db.execute(
            """
            SELECT
                COALESCE(SUM(stock), 0) AS seed_stock,
                COUNT(CASE WHEN stock > 0 THEN 1 END) AS lots_in_stock,
                COUNT(DISTINCT CASE WHEN stock > 0 THEN cultivar_id END)
                    AS cultivars_in_stock
            FROM (
                SELECT
                    s.id,
                    s.cultivar_id,
                    COALESCE(SUM(m.quantity), 0) AS stock
                FROM pm_seed_lots s
                LEFT JOIN pm_seed_movements m ON m.seed_lot_id = s.id
                WHERE s.status != 'archived'
                GROUP BY s.id
            )
            """
        ).fetchone()

        active_runs = db.execute(
            """
            SELECT COUNT(*) AS count
            FROM pm_propagation_runs
            WHERE status = 'active'
            """
        ).fetchone()["count"]

        active_mothers = db.execute(
            """
            SELECT COUNT(*) AS count
            FROM pm_plants
            WHERE status = 'active'
              AND current_role IN ('mother', 'donor')
            """
        ).fetchone()["count"]

        success = db.execute(
            """
            SELECT
                r.method,
                SUM(
                    CASE
                        WHEN (
                            r.method = 'seed'
                            AND u.status IN ('germinated', 'plant_created')
                        ) OR (
                            r.method = 'cutting'
                            AND u.status IN ('rooted', 'plant_created')
                        )
                        THEN 1 ELSE 0
                    END
                ) AS successful,
                SUM(CASE WHEN u.status = 'failed' THEN 1 ELSE 0 END) AS failed
            FROM pm_propagation_runs r
            JOIN pm_propagation_units u ON u.run_id = r.id
            GROUP BY r.method
            """
        ).fetchall()

        rates = {"seed": None, "cutting": None}
        for row in success:
            successful = int(row["successful"] or 0)
            failed = int(row["failed"] or 0)
            decided = successful + failed
            rates[row["method"]] = (
                round(successful / decided * 100, 1)
                if decided
                else None
            )

        return {
            "seed_stock": int(seed_row["seed_stock"] or 0),
            "lots_in_stock": int(seed_row["lots_in_stock"] or 0),
            "cultivars_in_stock": int(seed_row["cultivars_in_stock"] or 0),
            "active_runs": int(active_runs or 0),
            "active_mothers": int(active_mothers or 0),
            "germination_rate": rates["seed"],
            "rooting_rate": rates["cutting"],
        }
    finally:
        db.close()
