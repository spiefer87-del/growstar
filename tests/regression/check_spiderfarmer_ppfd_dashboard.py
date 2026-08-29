#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)

def main():
    sensor_sources = (ROOT / "core/sensor_sources.py").read_text(encoding="utf-8")
    spiderfarmer = (ROOT / "services/spiderfarmer.py").read_text(encoding="utf-8")
    tents = (ROOT / "routes/tents.py").read_text(encoding="utf-8")
    template = (ROOT / "templates/grow_control.html").read_text(encoding="utf-8")

    require("ppfd=None" in sensor_sources, "Sensorquelle akzeptiert PPFD")
    require('source["ppfd"] = float(ppfd)' in sensor_sources, "PPFD wird normalisiert gespeichert")
    require('ppfd = sensor.get(' in spiderfarmer, "Spider-Farmer Readmodel publiziert PPFD")
    require("ppfd=ppfd" in spiderfarmer, "PPFD gelangt in Growstar sensor_sources")
    require("def _assigned_spiderfarmer_ppfd(runtime):" in tents, "Stationsbezogene PPFD-Auflösung vorhanden")
    require('"light_ppfd": light_ppfd' in tents, "Tent-State liefert PPFD")
    require('"light_ppfd_source": light_ppfd_source' in tents, "Tent-State liefert PPFD-Quelle")
    require("µmol/m²/s" in template, "Dashboard verwendet korrekte PPFD-Einheit")
    require(
        '"light-level"' in template and "state.light_ppfd" in template,
        "Dashboard aktualisiert vorbereitete Helligkeits-Kachel",
    )
    require("> lx</div>" not in template, "Kein falsches Lux-Label auf der PPFD-Kachel")

    print("✅ Growstar 3.13.10 / PPFD.1 vollständig geprüft")

if __name__ == "__main__":
    main()
