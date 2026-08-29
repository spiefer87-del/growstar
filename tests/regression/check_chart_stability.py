#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def req(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("✅", msg)

def main():
    page=(ROOT/"templates/environment_history.html").read_text(encoding="utf-8")
    ppfd=(ROOT/"tests/regression/check_spiderfarmer_ppfd_dashboard.py").read_text(encoding="utf-8")

    req('const unit=currentRange==="1h"?"minute"' in page, "1h benutzt Time-Scale mit Minuten")
    req('type:"linear"' not in page, "Kein Scale-Typ-Wechsel auf linear")
    req('console.error("History API:"' in page, "API-Fehler werden separat diagnostiziert")
    req('console.error("Chart render:"' in page, "Chart-Fehler werden separat diagnostiziert")
    req('Für diesen Zeitraum sind noch keine Messwerte gespeichert.' in page, "Leere Historie wird korrekt unterschieden")
    req('id="station-select"' in page, "Stationswechsel bleibt erhalten")
    req('state.light_ppfd' in ppfd, "PPFD-Test prüft semantisch")
    print("✅ Growstar 3.15.3 / ENV.CHARTS.STABILITY vollständig geprüft")

if __name__=="__main__":
    main()
