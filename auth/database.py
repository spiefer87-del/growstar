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


def _db():
    db = get_db()
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 10000")
    return db


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
            password_changed_at INTEGER NOT NULL
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            description TEXT,
            created_at INTEGER NOT NULL
        )
        """
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
            "INSERT OR IGNORE INTO permissions (name, description, created_at) VALUES (?, ?, ?)",
            (name, description, now),
        )

    created_roles = set()
    for role_name, role_data in DEFAULT_ROLES.items():
        before = db.total_changes
        c.execute(
            "INSERT OR IGNORE INTO roles (name, description, created_at) VALUES (?, ?, ?)",
            (role_name, role_data["description"], now),
        )
        if db.total_changes > before:
            created_roles.add(role_name)

    # Neue Standardrollen bekommen beim ersten Anlegen ihr Start-Rechteset.
    for role_name in created_roles:
        if role_name == "Administrator":
            continue
        for permission_name in DEFAULT_ROLES[role_name]["permissions"]:
            c.execute(
                """
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id
                FROM roles r, permissions p
                WHERE r.name = ? AND p.name = ?
                """,
                (role_name, permission_name),
            )

    # Administrator bleibt absichtlich eine Vollzugriffsrolle. Neue Permissions
    # werden deshalb beim Start automatisch ergänzt.
    c.execute(
        """
        INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name = 'Administrator'
        """
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
        ORDER BY r.name
        """,
        (user_id,),
    ).fetchall()
    db.close()
    return [row["name"] for row in rows]


def get_user_permissions(user_id):
    db = _db()
    rows = db.execute(
        """
        SELECT DISTINCT p.name
        FROM permissions p
        JOIN role_permissions rp ON rp.permission_id = p.id
        JOIN user_roles ur ON ur.role_id = rp.role_id
        WHERE ur.user_id = ?
        ORDER BY p.name
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
                created_at, updated_at, password_changed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
