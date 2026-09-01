#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

def req(c, m):
    if not c:
        raise AssertionError(m)
    print("✅", m)

def main():
    html = (ROOT/"templates/grow_control.html").read_text(encoding="utf-8")
    req('id="light-level-card"' in html, "Helligkeits-Kachel bleibt vorhanden")
    req('class="card-link ppfd-card-shell" id="light-level-link"' in html, "Eigene PPFD-Kachelstruktur aktiv")
    req('<div class="sub ppfd-unit">µmol/m²/s</div>' in html, "Einheit steht dezent unter dem Wert")
    req(".ppfd-unit{" in html, "Eigener kleiner PPFD-Einheitenstil vorhanden")

    m = re.search(
        r'<a\s+[^>]*class="card-link ppfd-card-shell"\s+'
        r'id="light-level-link"[^>]*>.*?</a>',
        html,
        re.S,
    )
    req(m is not None, "PPFD-Kachelblock gefunden")
    block = m.group(0)

    req("Spider Farmer" not in block, "Sensorname aus Kachel entfernt")
    req("Zelt-Detail folgt" not in block, "Zelt-Detail-Hinweis aus Kachel entfernt")
    req("pending-detail-link" not in block, "Kachel nicht mehr pending-gesperrt")
    req(" lx" not in block and ">Sensor<" not in block, "Alte lx/Sensor-Platzhalter entfernt")

    print("✅ Growstar 3.14.3 / DASH.PPFD.CARD.1 vollständig geprüft")

if __name__ == "__main__":
    main()
