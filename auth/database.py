import json
import sqlite3
import time

from db import get_db


PERMISSIONS = {
    "dashboard.view": "Dashboard anzeigen",
    "grow.view": "Grow-Daten anzeigen",
    "grow.control": "Grow-Geräte manuell steuern",
    "grow.configure": "Grow-Regelung konfigurieren",
    "plants.view": "Pflanzendaten anzeigen",
    "plants.edit": "Pflanzendaten bearbeiten",
    "diary.view": "Tagebuch anzeigen",
    "diary.edit": "Tagebuch bearbeiten",
    "hardware.view": "Hardware anzeigen",
    "hardware.control": "Hardware steuern",
    "hardware.configure": "Hardware konfigurieren",
    "inventory.view": "Lagerbestände anzeigen",
    "inventory.create": "Lagerartikel anlegen",
    "inventory.edit": "Lagerartikel bearbeiten",
    "inventory.adjust": "Bestände korrigieren",
    "receiving.view": "Warenannahmen anzeigen",
    "receiving.create": "Warenannahmen buchen",
    "receiving.edit": "Warenannahmen bearbeiten",
    "suppliers.view": "Lieferanten anzeigen",
    "suppliers.edit": "Lieferanten bearbeiten",
    "users.view": "Benutzer anzeigen",
    "users.manage": "Benutzer verwalten",
    "roles.view": "Rollen anzeigen",
    "roles.manage": "Rollen und Rechte verwalten",
    "settings.view": "Einstellungen anzeigen",
    "settings.manage": "Einstellungen bearbeiten",
    "audit.view": "Audit-Protokoll anzeigen",
}


DEFAULT_ROLES = {
    "Administrator": {
        "description": "Vollzugriff auf Growstar",
        "permissions": "*",
    },
    "Manager": {
        "description": "Betrieb, Grow, Lager und Warenannahme verwalten",
        "permissions": {
            "dashboard.view",
            "grow.view",
            "grow.control",
            "grow.configure",
            "plants.view",
            "plants.edit",
            "diary.view",
            "diary.edit",
            "hardware.view",
            "hardware.control",
            "inventory.view",
            "inventory.create",
            "inventory.edit",
            "inventory.adjust",
            "receiving.view",
            "receiving.create",
            "receiving.edit",
            "suppliers.view",
            "suppliers.edit",
            "settings.view",
        },
    },
    "Operator": {
        "description": "Grow bedienen und Betriebsdaten pflegen",
        "permissions": {
            "dashboard.view",
            "grow.view",
            "grow.control",
            "plants.view",
            "plants.edit",
            "diary.view",
            "diary.edit",
            "hardware.view",
            "hardware.control",
        },
    },
    "Warehouse": {
        "description": "Lager und Warenannahme",
        "permissions": {
            "dashboard.view",
            "inventory.view",
            "inventory.create",
            "inventory.edit",
            "receiving.view",
            "receiving.create",
            "receiving.edit",
            "suppliers.view",
        },
    },
    "Viewer": {
        "description": "Nur lesender Zugriff",
        "permissions": {
            "dashboard.view",
            "grow.view",
            "plants.view",
            "diary.view",
            "hardware.view",
            "inventory.view",
            "receiving.view",
            "suppliers.view",
            "settings.view",
        },
    },
}


ADMIN_ROLE_NAME = "Administrator"


def _db():
    db = get_db()
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 10000")
    return db


def _column_names(db, table_name):
    return {row[1] for row in db.execute(f"PRAGMA table_info({table_name})")}


def init_auth_db():
    """Legt Auth-, Rollen- und Audit-Tabellen in der bestehenden data.db an."""

    db = _db()
    c = db.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            email TEXT COLLATE NOCASE UNIQUE,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            last_login_at INTEGER,
            password_changed_at INTEGER NOT NULL,
            session_version INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    # Migration von Phase 1: bestehende Sessions können nach Passwortwechsel
    # gezielt ungültig gemacht werden.
    user_columns = _column_names(db, "users")
    if "session_version" not in user_columns:
        c.execute(
            "ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 1"
        )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            description TEXT,
            created_at INTEGER NOT NULL,
            is_system INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    # Migration von Phase 1: Standardrollen werden vor versehentlichem
    # Umbenennen geschützt. Ihre Rechte bleiben (außer Administrator) editierbar.
    role_columns = _column_names(db, "roles")
    if "is_system" not in role_columns:
        c.execute(
            "ALTER TABLE roles ADD COLUMN is_system INTEGER NOT NULL DEFAULT 0"
        )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            description TEXT,
            created_at INTEGER NOT NULL
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, role_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id INTEGER NOT NULL,
            permission_id INTEGER NOT NULL,
            PRIMARY KEY (role_id, permission_id),
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
            FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            details TEXT,
            ip_address TEXT,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )

    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_log(created_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_user_id ON audit_log(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)")

    now = int(time.time())

    for name, description in PERMISSIONS.items():
        c.execute(
            """
            INSERT OR IGNORE INTO permissions (name, description, created_at)
            VALUES (?, ?, ?)
            """,
            (name, description, now),
        )
        c.execute(
            "UPDATE permissions SET description = ? WHERE name = ? COLLATE NOCASE",
            (description, name),
        )

    created_roles = set()
    for role_name, role_data in DEFAULT_ROLES.items():
        before = db.total_changes
        c.execute(
            """
            INSERT OR IGNORE INTO roles (name, description, created_at, is_system)
            VALUES (?, ?, ?, 1)
            """,
            (role_name, role_data["description"], now),
        )
        if db.total_changes > before:
            created_roles.add(role_name)

        c.execute(
            "UPDATE roles SET is_system = 1 WHERE name = ? COLLATE NOCASE",
            (role_name,),
        )

    # Start-Rechteset nur bei neu angelegten Standardrollen. Änderungen an
    # Manager/Operator/Warehouse/Viewer bleiben damit erhalten.
    for role_name in created_roles:
        if role_name == ADMIN_ROLE_NAME:
            continue
        for permission_name in DEFAULT_ROLES[role_name]["permissions"]:
            c.execute(
                """
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id
                FROM roles r, permissions p
                WHERE r.name = ? COLLATE NOCASE AND p.name = ? COLLATE NOCASE
                """,
                (role_name, permission_name),
            )

    # Administrator ist bewusst unveränderlicher Vollzugriff. Neue Permissions
    # werden beim Start automatisch ergänzt.
    c.execute(
        """
        INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name = ? COLLATE NOCASE
        """,
        (ADMIN_ROLE_NAME,),
    )

    db.commit()
    db.close()


def get_user_by_username(username):
    db = _db()
    row = db.execute(
        "SELECT * FROM users WHERE username = ? COLLATE NOCASE",
        (username.strip(),),
    ).fetchone()
    db.close()
    return dict(row) if row else None


def get_user_by_id(user_id):
    db = _db()
    row = db.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    db.close()
    return dict(row) if row else None


def get_user_roles(user_id):
    db = _db()
    rows = db.execute(
        """
        SELECT r.name
        FROM roles r
        JOIN user_roles ur ON ur.role_id = r.id
        WHERE ur.user_id = ?
        ORDER BY r.name COLLATE NOCASE
        """,
        (user_id,),
    ).fetchall()
    db.close()
    return [row["name"] for row in rows]


def get_user_role_ids(user_id):
    db = _db()
    rows = db.execute(
        "SELECT role_id FROM user_roles WHERE user_id = ? ORDER BY role_id",
        (user_id,),
    ).fetchall()
    db.close()
    return [row["role_id"] for row in rows]


def get_user_permissions(user_id):
    db = _db()
    rows = db.execute(
        """
        SELECT DISTINCT p.name
        FROM permissions p
        JOIN role_permissions rp ON rp.permission_id = p.id
        JOIN user_roles ur ON ur.role_id = rp.role_id
        WHERE ur.user_id = ?
        ORDER BY p.name COLLATE NOCASE
        """,
        (user_id,),
    ).fetchall()
    db.close()
    return [row["name"] for row in rows]


def load_user(user_id):
    user = get_user_by_id(user_id)
    if not user or not user["is_active"]:
        return None

    user["roles"] = get_user_roles(user_id)
    user["permissions"] = get_user_permissions(user_id)
    return user


def list_users():
    db = _db()
    rows = db.execute(
        """
        SELECT *
        FROM users
        ORDER BY is_active DESC, username COLLATE NOCASE
        """
    ).fetchall()
    db.close()

    users = []
    for row in rows:
        user = dict(row)
        user["roles"] = get_user_roles(user["id"])
        users.append(user)
    return users


def create_user(username, display_name, password_hash, email=None, is_active=True):
    username = username.strip()
    display_name = display_name.strip()
    email = email.strip() if email else None

    if not username:
        raise ValueError("Benutzername darf nicht leer sein")
    if not display_name:
        raise ValueError("Anzeigename darf nicht leer sein")

    now = int(time.time())
    db = _db()
    try:
        cur = db.execute(
            """
            INSERT INTO users (
                username, email, display_name, password_hash, is_active,
                created_at, updated_at, password_changed_at, session_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                username,
                email,
                display_name,
                password_hash,
                1 if is_active else 0,
                now,
                now,
                now,
            ),
        )
        db.commit()
        return cur.lastrowid
    finally:
        db.close()


def update_user(user_id, username, display_name, email=None):
    username = username.strip()
    display_name = display_name.strip()
    email = email.strip() if email else None

    if not username:
        raise ValueError("Benutzername darf nicht leer sein")
    if not display_name:
        raise ValueError("Anzeigename darf nicht leer sein")

    db = _db()
    try:
        db.execute(
            """
            UPDATE users
            SET username = ?, display_name = ?, email = ?, updated_at = ?
            WHERE id = ?
            """,
            (username, display_name, email, int(time.time()), user_id),
        )
        db.commit()
    finally:
        db.close()


def set_user_active(user_id, is_active):
    db = _db()
    try:
        # Deaktivieren invalidiert sofort alle bestehenden Sessions.
        if is_active:
            db.execute(
                "UPDATE users SET is_active = 1, updated_at = ? WHERE id = ?",
                (int(time.time()), user_id),
            )
        else:
            db.execute(
                """
                UPDATE users
                SET is_active = 0,
                    updated_at = ?,
                    session_version = session_version + 1
                WHERE id = ?
                """,
                (int(time.time()), user_id),
            )
        db.commit()
    finally:
        db.close()


def set_user_password_hash(user_id, password_hash):
    now = int(time.time())
    db = _db()
    try:
        db.execute(
            """
            UPDATE users
            SET password_hash = ?,
                password_changed_at = ?,
                updated_at = ?,
                session_version = session_version + 1
            WHERE id = ?
            """,
            (password_hash, now, now, user_id),
        )
        row = db.execute(
            "SELECT session_version FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        db.commit()
        return row["session_version"] if row else None
    finally:
        db.close()


def assign_role(user_id, role_name):
    db = _db()
    try:
        role = db.execute(
            "SELECT id FROM roles WHERE name = ? COLLATE NOCASE",
            (role_name,),
        ).fetchone()
        if not role:
            raise ValueError(f"Unbekannte Rolle: {role_name}")

        db.execute(
            "INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)",
            (user_id, role["id"]),
        )
        db.commit()
    finally:
        db.close()


def set_user_roles(user_id, role_ids):
    role_ids = sorted({int(role_id) for role_id in role_ids})
    db = _db()
    try:
        if role_ids:
            placeholders = ",".join("?" for _ in role_ids)
            rows = db.execute(
                f"SELECT id FROM roles WHERE id IN ({placeholders})",
                role_ids,
            ).fetchall()
            if len(rows) != len(role_ids):
                raise ValueError("Mindestens eine ausgewählte Rolle ist unbekannt")

        db.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
        db.executemany(
            "INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)",
            [(user_id, role_id) for role_id in role_ids],
        )
        db.commit()
    finally:
        db.close()


def get_role_by_id(role_id):
    db = _db()
    row = db.execute(
        "SELECT * FROM roles WHERE id = ?",
        (role_id,),
    ).fetchone()
    db.close()
    if not row:
        return None

    role = dict(row)
    role["permissions"] = get_role_permissions(role_id)
    return role


def get_role_by_name(role_name):
    db = _db()
    row = db.execute(
        "SELECT * FROM roles WHERE name = ? COLLATE NOCASE",
        (role_name,),
    ).fetchone()
    db.close()
    return dict(row) if row else None


def get_role_permissions(role_id):
    db = _db()
    rows = db.execute(
        """
        SELECT p.id, p.name, p.description
        FROM permissions p
        JOIN role_permissions rp ON rp.permission_id = p.id
        WHERE rp.role_id = ?
        ORDER BY p.name COLLATE NOCASE
        """,
        (role_id,),
    ).fetchall()
    db.close()
    return [dict(row) for row in rows]


def get_role_permission_ids(role_id):
    return [item["id"] for item in get_role_permissions(role_id)]


def list_roles():
    db = _db()
    rows = db.execute(
        """
        SELECT r.*,
               COUNT(DISTINCT ur.user_id) AS user_count,
               COUNT(DISTINCT rp.permission_id) AS permission_count
        FROM roles r
        LEFT JOIN user_roles ur ON ur.role_id = r.id
        LEFT JOIN role_permissions rp ON rp.role_id = r.id
        GROUP BY r.id
        ORDER BY r.is_system DESC, r.name COLLATE NOCASE
        """
    ).fetchall()
    db.close()
    return [dict(row) for row in rows]


def list_permissions():
    db = _db()
    rows = db.execute(
        "SELECT id, name, description FROM permissions ORDER BY name COLLATE NOCASE"
    ).fetchall()
    db.close()
    return [dict(row) for row in rows]


def create_role(name, description=None):
    name = name.strip()
    description = description.strip() if description else None
    if not name:
        raise ValueError("Rollenname darf nicht leer sein")

    db = _db()
    try:
        cur = db.execute(
            """
            INSERT INTO roles (name, description, created_at, is_system)
            VALUES (?, ?, ?, 0)
            """,
            (name, description, int(time.time())),
        )
        db.commit()
        return cur.lastrowid
    finally:
        db.close()


def update_role(role_id, name, description=None):
    role = get_role_by_id(role_id)
    if not role:
        raise ValueError("Rolle wurde nicht gefunden")

    name = name.strip()
    description = description.strip() if description else None
    if not name:
        raise ValueError("Rollenname darf nicht leer sein")

    # Systemrollen behalten ihren stabilen Namen. So kann init_auth_db sie bei
    # späteren Starts nicht versehentlich duplizieren.
    if role["is_system"]:
        name = role["name"]

    db = _db()
    try:
        db.execute(
            "UPDATE roles SET name = ?, description = ? WHERE id = ?",
            (name, description, role_id),
        )
        db.commit()
    finally:
        db.close()


def set_role_permissions(role_id, permission_ids):
    role = get_role_by_id(role_id)
    if not role:
        raise ValueError("Rolle wurde nicht gefunden")

    db = _db()
    try:
        # Administrator bleibt immer Vollzugriff.
        if role["name"].casefold() == ADMIN_ROLE_NAME.casefold():
            rows = db.execute("SELECT id FROM permissions").fetchall()
            permission_ids = [row["id"] for row in rows]
        else:
            permission_ids = sorted({int(pid) for pid in permission_ids})
            if permission_ids:
                placeholders = ",".join("?" for _ in permission_ids)
                rows = db.execute(
                    f"SELECT id FROM permissions WHERE id IN ({placeholders})",
                    permission_ids,
                ).fetchall()
                if len(rows) != len(permission_ids):
                    raise ValueError("Mindestens eine ausgewählte Berechtigung ist unbekannt")

        db.execute("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
        db.executemany(
            "INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
            [(role_id, pid) for pid in permission_ids],
        )
        db.commit()
    finally:
        db.close()


def is_user_administrator(user_id):
    return any(
        role.casefold() == ADMIN_ROLE_NAME.casefold()
        for role in get_user_roles(user_id)
    )


def count_active_administrators():
    db = _db()
    row = db.execute(
        """
        SELECT COUNT(DISTINCT u.id) AS amount
        FROM users u
        JOIN user_roles ur ON ur.user_id = u.id
        JOIN roles r ON r.id = ur.role_id
        WHERE u.is_active = 1 AND r.name = ? COLLATE NOCASE
        """,
        (ADMIN_ROLE_NAME,),
    ).fetchone()
    db.close()
    return int(row["amount"] if row else 0)


def update_last_login(user_id):
    now = int(time.time())
    db = _db()
    try:
        db.execute(
            "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
            (now, now, user_id),
        )
        db.commit()
    finally:
        db.close()


def get_admin_stats():
    db = _db()
    row = db.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM users) AS users_total,
            (SELECT COUNT(*) FROM users WHERE is_active = 1) AS users_active,
            (SELECT COUNT(*) FROM roles) AS roles_total,
            (SELECT COUNT(*) FROM permissions) AS permissions_total,
            (SELECT COUNT(*) FROM audit_log) AS audit_total
        """
    ).fetchone()
    db.close()
    return dict(row)


def list_audit_entries(limit=200, search=None):
    limit = max(1, min(int(limit), 500))
    db = _db()

    params = []
    where = ""
    if search:
        needle = f"%{search.strip()}%"
        where = """
        WHERE a.action LIKE ? COLLATE NOCASE
           OR COALESCE(u.username, '') LIKE ? COLLATE NOCASE
           OR COALESCE(a.entity_type, '') LIKE ? COLLATE NOCASE
           OR COALESCE(a.entity_id, '') LIKE ? COLLATE NOCASE
        """
        params.extend([needle, needle, needle, needle])

    params.append(limit)
    rows = db.execute(
        f"""
        SELECT a.*, u.username, u.display_name
        FROM audit_log a
        LEFT JOIN users u ON u.id = a.user_id
        {where}
        ORDER BY a.id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    db.close()

    result = []
    for row in rows:
        item = dict(row)
        if item.get("details"):
            try:
                item["details_data"] = json.loads(item["details"])
            except (TypeError, json.JSONDecodeError):
                item["details_data"] = item["details"]
        else:
            item["details_data"] = None
        result.append(item)
    return result


def write_audit(
    action,
    user_id=None,
    entity_type=None,
    entity_id=None,
    details=None,
    ip_address=None,
):
    payload = None
    if details is not None:
        payload = json.dumps(details, ensure_ascii=False, separators=(",", ":"))

    db = _db()
    try:
        db.execute(
            """
            INSERT INTO audit_log (
                user_id, action, entity_type, entity_id,
                details, ip_address, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                action,
                entity_type,
                None if entity_id is None else str(entity_id),
                payload,
                ip_address,
                int(time.time()),
            ),
        )
        db.commit()
    finally:
        db.close()
