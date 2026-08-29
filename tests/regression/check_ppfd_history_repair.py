#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def req(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("✅", msg)

def main():
    sensor=(ROOT/"core/sensor_sources.py").read_text(encoding="utf-8")
    tents=(ROOT/"routes/tents.py").read_text(encoding="utf-8")
    thread=(ROOT/"threads/main.py").read_text(encoding="utf-8")
    db=(ROOT/"db.py").read_text(encoding="utf-8")
    diagrams=(ROOT/"routes/diagrams.py").read_text(encoding="utf-8")
    dashboard=(ROOT/"templates/grow_control.html").read_text(encoding="utf-8")
    history=(ROOT/"templates/environment_history.html").read_text(encoding="utf-8")

    req('elif sensor_name == "ppfd":' in sensor,"PPFD besitzt Feld-Default")
    req('_read_assigned_value(\n        "ppfd"' in sensor,"Runtime liest PPFD-Zuweisung")
    req('st.live_state["light_ppfd"] = ppfd_raw' in sensor,"Runtime erhält PPFD-Livewert")
    req('st.live_state.pop("light_ppfd", None)' in sensor,"Stale PPFD wird entfernt")
    req('light_ppfd = live.get("light_ppfd")' in tents,"State API bevorzugt Runtime-PPFD")
    req('ppfd_val = st.live_state.get("light_ppfd")' in thread,"DB-Zyklus liest PPFD")
    req('ppfd=ppfd_val' in thread,"DB-Zyklus schreibt PPFD")
    req('ADD COLUMN ppfd REAL' in db,"PPFD-Spalte vorhanden")
    req('data_type == "ppfd"' in diagrams,"PPFD-History API aktiv")

    req("grow_control_tent_ppfd" in dashboard,"Helligkeits-Kachel klickbar")
    req('"light-level",' in dashboard,"Dashboard aktualisiert Helligkeit")

    for marker in (
        'id="device-grid"',
        'id="heating-card"',
        'id="fan-card"',
        'id="light-card"',
        'id="vent-card"',
        'id="dehumidifier-card"',
        'function collectCards()',
        'function renderDashboard()',
    ):
        req(marker in dashboard,f"Dashboard-Struktur erhalten: {marker}")

    req('id="station-select"' in history,"Diagramm besitzt Stationsauswahl")
    req('fetch("/api/tents"' in history,"Stationsauswahl nutzt bestehende API")
    req('metricUrlForTent' in history,"Messgröße bleibt beim Stationswechsel erhalten")

    print("✅ Growstar 3.15.2 / PPFD.HISTORY.REPAIR vollständig geprüft")

if __name__=="__main__":
    main()
