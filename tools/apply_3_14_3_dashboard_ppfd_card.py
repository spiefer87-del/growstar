#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates/grow_control.html"

def fail(msg):
    raise SystemExit("❌ " + msg)

def require(path, marker, label):
    p = ROOT / path
    if not p.exists():
        fail(f"{label}: Datei fehlt: {path}")
    text = p.read_text(encoding="utf-8")
    if marker not in text:
        fail(f"{label}: Marker fehlt in {path}")
    print("✅", label)

require("templates/grow_control.html", 'id="light-level-card"', "Helligkeits-Kachel vorhanden")
require("templates/grow_control.html", 'id="light-level"', "PPFD-Wertfeld vorhanden")
require("routes/tents.py", '"light_ppfd"', "Stationsbezogener PPFD-State vorhanden")

text = TEMPLATE.read_text(encoding="utf-8")

pattern = re.compile(
    r'<a\b[^>]*\bid=["\']light-level-link["\'][^>]*>.*?</a>',
    re.IGNORECASE | re.DOTALL,
)

replacement = """<div class="card-link ppfd-card-shell" id="light-level-link">
        <div class="card env" id="light-level-card">
            <h2>Helligkeit</h2>
            <div class="value ppfd-value"><span id="light-level">---</span></div>
            <div class="sub ppfd-unit">µmol/m²/s</div>
        </div>
    </div>"""

matches = list(pattern.finditer(text))
if len(matches) != 1:
    fail(f"Helligkeits-Kachel nicht eindeutig gefunden (Treffer: {len(matches)})")

m = matches[0]
old = m.group(0)
if 'ppfd-card-shell' not in old:
    text = text[:m.start()] + replacement + text[m.end():]
    print("✅ Helligkeits-Kachel bereinigt")
else:
    print("✅ Helligkeits-Kachel bereits bereinigt")

css = """
.ppfd-card-shell{
    color:inherit;
    text-decoration:none;
}
.ppfd-value{
    line-height:1.02;
}
.ppfd-unit{
    margin-top:4px;
    font-size:.72rem;
    font-weight:600;
    letter-spacing:.01em;
    color:var(--muted);
}
"""

if ".ppfd-unit{" not in text:
    anchor = ".sub { margin-top: 6px; font-size: .8rem; color: var(--muted); }"
    if anchor not in text:
        fail("CSS-Anker nicht gefunden")
    text = text.replace(anchor, anchor + "\n" + css, 1)
    print("✅ PPFD-Einheit kleiner formatiert")
else:
    print("✅ PPFD-CSS bereits vorhanden")

pos = text.find('id="light-level-link"')
window = text[max(0,pos-180):pos+220]
if "pending-detail-link" in window:
    fail("Helligkeits-Kachel besitzt weiterhin pending-detail-link")

TEMPLATE.write_text(text, encoding="utf-8")
print("✅ Growstar 3.14.3 / DASH.PPFD.CARD.1 vollständig angewendet")
