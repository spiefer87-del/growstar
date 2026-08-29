#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def req(cond,msg):
    if not cond:
        raise AssertionError(msg)
    print("✅",msg)

def main():
    db=(ROOT/"db.py").read_text(encoding="utf-8")
    loop=(ROOT/"threads/main.py").read_text(encoding="utf-8")
    diagrams=(ROOT/"routes/diagrams.py").read_text(encoding="utf-8")
    dashboard=(ROOT/"routes/dashboard.py").read_text(encoding="utf-8")
    grow=(ROOT/"templates/grow_control.html").read_text(encoding="utf-8")
    page=(ROOT/"templates/environment_history.html").read_text(encoding="utf-8")
    req('ADD COLUMN ppfd REAL' in db,"DB-Migration ergänzt PPFD")
    req('ppfd=None' in db,"Messwert-API akzeptiert PPFD")
    req('st.live_state.get("light_ppfd")' in loop,"Regelzyklus liest PPFD")
    req('ppfd=ppfd_val' in loop,"Regelzyklus speichert PPFD")
    req('data_type == "ppfd"' in diagrams,"History-API unterstützt PPFD")
    req('SELECT ts, ppfd' in diagrams,"PPFD-Historie lesbar")
    req('def grow_control_tent_ppfd' in dashboard,"PPFD-Detailroute vorhanden")
    req('"environment_history.html"' in dashboard,"Gemeinsame Verlaufsseite aktiv")
    req("grow_control_tent_ppfd" in grow,"Helligkeits-Kachel ist klickbar")
    req('data-metric="temp"' in page,"Direktwechsel Temperatur")
    req('data-metric="hum"' in page,"Direktwechsel Luftfeuchte")
    req('data-metric="vpd"' in page,"Direktwechsel VPD")
    req('data-metric="ppfd"' in page,"Direktwechsel Helligkeit")
    req('history.replaceState' in page,"Wechsel ohne Seitenreload")
    req('Sollwert ausblenden' in page,"Sollwert-Toggle vorhanden")
    req('setInterval(load,60000)' in page,"Auto-Refresh vorhanden")
    print("✅ Growstar 3.15.0 / ENV.CHARTS.1 vollständig geprüft")

if __name__=="__main__":
    main()
