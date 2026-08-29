#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def fail(msg):
    raise SystemExit("❌ " + msg)

def replace_once(path, old, new, label):
    p = ROOT / path
    if not p.exists():
        fail(f"{label}: Datei fehlt: {path}")

    text = p.read_text(encoding="utf-8")

    if new in text:
        print(f"✅ {label}: bereits vorhanden")
        return

    if old not in text:
        fail(f"{label}: erwarteter Codeblock fehlt in {path}")

    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("✅", label)

db_path = ROOT / "db.py"
db_text = db_path.read_text(encoding="utf-8")

for marker in (
    "ppfd=None",
    "ADD COLUMN ppfd REAL",
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
):
    if marker not in db_text:
        fail(f"db.py ist nicht auf dem erwarteten 3.15.x-Stand: {marker}")

print("✅ db.py besitzt PPFD-Schema und 8 SQL-Platzhalter")

replace_once(
    "db.py",
    '''        (
            tent_id,
            int(time.time()),
            temp,
            temp_target,
            hum,
            hum_target,
            vpd
        )
''',
    '''        (
            tent_id,
            int(time.time()),
            temp,
            temp_target,
            hum,
            hum_target,
            vpd,
            ppfd
        )
''',
    "Fehlendes PPFD-Binding in insert_measurement ergänzt",
)

test_path = ROOT / "tests/regression/check_spiderfarmer_ppfd_dashboard.py"
if test_path.exists():
    test_text = test_path.read_text(encoding="utf-8")
    old = "    require('safeText(\"light-level\"' in template, \"Dashboard aktualisiert vorbereitete Helligkeits-Kachel\")"
    new = '''    require(
        '"light-level"' in template and "state.light_ppfd" in template,
        "Dashboard aktualisiert vorbereitete Helligkeits-Kachel",
    )'''
    if old in test_text and new not in test_text:
        test_path.write_text(test_text.replace(old, new, 1), encoding="utf-8")
        print("✅ Alter formatabhängiger PPFD-Dashboard-Test korrigiert")
    elif new in test_text:
        print("✅ PPFD-Dashboard-Test bereits korrigiert")
    else:
        print("ℹ️ PPFD-Dashboard-Test hat bereits einen anderen aktuellen Stand")

print("✅ Growstar 3.15.4 / HISTORY.BINDING.FIX vollständig angewendet")
