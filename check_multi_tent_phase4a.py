from pathlib import Path

path = Path(__file__).parent / "templates" / "dashboard.html"
text = path.read_text(encoding="utf-8")

checks = {
    "Multi-Tent API wird gelesen": 'fetch("/api/tents"' in text,
    "Zeltübersicht vorhanden": 'id="tent-overview-grid"' in text,
    "LIVE-Badge vorhanden": 'text: "LIVE"' in text,
    "SHADOW-Badge vorhanden": 'text: "SHADOW"' in text,
    "Default-Zelt darf Grow Control öffnen": "tent.id === defaultTentId" in text,
    "Nicht-Default-Zelte bleiben read-only": 'readOnly.textContent = "Nur Anzeige"' in text,
    "Daten werden ohne innerHTML aufgebaut": "grid.replaceChildren()" in text,
    "Auto-Refresh aktiv": "setInterval(loadTents, 5000)" in text,
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(("✅" if ok else "❌"), name)

if failed:
    raise SystemExit("Phase 4A fehlgeschlagen: " + ", ".join(failed))

print("✅ Phase 4A Dashboard-Zeltübersicht vollständig")
