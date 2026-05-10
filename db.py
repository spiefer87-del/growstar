import sqlite3
import time

DB_FILE = "data.db"


def get_db():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


def init_db():
    db = get_db()
    c = db.cursor()

    # Basis-Tabelle (falls DB neu ist)
    c.execute("""
        CREATE TABLE IF NOT EXISTS temp_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER,
            temp REAL,
            temp_target REAL,
            hum REAL,
            hum_target REAL,
            vpd REAL
        )
    """)

    # 🔧 Migration für bestehende DBs (ALTER TABLE ist safe)
    existing_cols = [row[1] for row in c.execute("PRAGMA table_info(temp_history)")]

    if "hum" not in existing_cols:
        c.execute("ALTER TABLE temp_history ADD COLUMN hum REAL")

    if "hum_target" not in existing_cols:
        c.execute("ALTER TABLE temp_history ADD COLUMN hum_target REAL")

    if "vpd" not in existing_cols:
        c.execute("ALTER TABLE temp_history ADD COLUMN vpd REAL")

    db.commit()
    db.close()


def insert_measurement(
    temp,
    temp_target,
    hum=None,
    hum_target=None,
    vpd=None
):
    """
    Speichert einen kompletten Messpunkt:
    - Temperatur
    - Luftfeuchte
    - VPD
    """
    db = get_db()
    c = db.cursor()

    c.execute(
        """
        INSERT INTO temp_history (
            ts,
            temp,
            temp_target,
            hum,
            hum_target,
            vpd
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            int(time.time()),
            temp,
            temp_target,
            hum,
            hum_target,
            vpd
        )
    )

    db.commit()
    db.close()

# =========================================
# 📔 TAGEBUCH-FUNKTIONEN
# =========================================

def init_diary_db():
    db = sqlite3.connect("data.db")
    c = db.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS diary_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            plant INTEGER,
            action TEXT,
            ph REAL,
            ec REAL,
            amount REAL,
            note TEXT
        )
    """)

    db.commit()
    db.close()

# =========================================
# 🌿 PFLANZEN-PROFILE
# =========================================

def init_plants_table():
    db = sqlite3.connect("data.db")
    c = db.cursor()

    # Tabelle anlegen (Basis)
    c.execute("""
        CREATE TABLE IF NOT EXISTS plants (
            id INTEGER PRIMARY KEY,
            name TEXT
        )
    """)

    # Spalten nachträglich hinzufügen (wenn sie fehlen)
    def add_column(col_name, col_type):
        try:
            c.execute(f"ALTER TABLE plants ADD COLUMN {col_name} {col_type}")
            print(f"✅ plants: Spalte hinzugefügt → {col_name}")
        except Exception:
            pass  # Spalte existiert schon

    add_column("sativa", "INTEGER")
    add_column("indica", "INTEGER")
    add_column("seed_date", "TEXT")
    add_column("flower_days", "INTEGER")
    add_column("flower_start", "TEXT")

    # 6 Slots sicherstellen
    for i in range(1, 7):
        c.execute("INSERT OR IGNORE INTO plants (id, name) VALUES (?, ?)", (i, f"Pflanze {i}"))

    db.commit()
    db.close()
