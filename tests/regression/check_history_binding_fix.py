#!/usr/bin/env python3
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def req(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("✅", msg)


def main():
    import db as grow_db

    source = (ROOT / "db.py").read_text(encoding="utf-8")

    req("ppfd=None" in source, "insert_measurement akzeptiert PPFD")
    req("VALUES (?, ?, ?, ?, ?, ?, ?, ?)" in source, "SQL besitzt exakt 8 Platzhalter")
    req(
        "            vpd,\\n            ppfd\\n" in source,
        "Binding-Tupel enthält VPD und PPFD",
    )

    old_db_file = grow_db.DB_FILE

    with tempfile.TemporaryDirectory() as tmp:
        test_db = Path(tmp) / "history_binding.db"
        grow_db.DB_FILE = str(test_db)

        try:
            grow_db.init_db()

            grow_db.insert_measurement(
                temp=24.5,
                temp_target=24.0,
                hum=62.5,
                hum_target=60.0,
                vpd=1.12,
                ppfd=245.0,
                tent_id="tent_test",
            )

            con = sqlite3.connect(test_db)
            row = con.execute(
                '''
                SELECT tent_id, temp, temp_target, hum, hum_target, vpd, ppfd
                FROM temp_history
                WHERE tent_id = ?
                ORDER BY id DESC
                LIMIT 1
                ''',
                ("tent_test",),
            ).fetchone()
            con.close()

            req(row is not None, "Echter SQLite-Insert erzeugt einen Messpunkt")
            req(row[0] == "tent_test", "Tent-ID wird korrekt gespeichert")
            req(abs(row[1] - 24.5) < 0.001, "Temperatur wird korrekt gespeichert")
            req(abs(row[2] - 24.0) < 0.001, "Temperatur-Sollwert wird korrekt gespeichert")
            req(abs(row[3] - 62.5) < 0.001, "Luftfeuchtigkeit wird korrekt gespeichert")
            req(abs(row[4] - 60.0) < 0.001, "Feuchte-Sollwert wird korrekt gespeichert")
            req(abs(row[5] - 1.12) < 0.001, "VPD wird korrekt gespeichert")
            req(abs(row[6] - 245.0) < 0.001, "PPFD wird korrekt gespeichert")

        finally:
            grow_db.DB_FILE = old_db_file

    print("✅ Growstar 3.15.4 / HISTORY.BINDING.FIX vollständig geprüft")


if __name__ == "__main__":
    main()
