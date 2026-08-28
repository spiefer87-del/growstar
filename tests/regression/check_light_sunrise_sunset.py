#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.light_sun import calculate_light_sun_state

def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)

def main():
    common = dict(
        day_start=360,
        night_start=1320,
        sunrise_duration=60,
        sunset_duration=60,
        min_level=11,
        target_level=80,
    )

    s = calculate_light_sun_state(now_min=359, **common)
    require(s["on"] is False, "Vor Tag Start bleibt Licht AUS")

    s = calculate_light_sun_state(now_min=360, **common)
    require(s["on"] and s["phase"] == "sunrise", "Tag Start beginnt Sonnenaufgang")
    require(s["level"] == 11, "Sonnenaufgang beginnt bei Mindestleistung")

    s = calculate_light_sun_state(now_min=390, **common)
    require(11 < s["level"] < 80, "Sonnenaufgang dimmt stufenweise nach oben")

    s = calculate_light_sun_state(now_min=420, **common)
    require(s["level"] == 80, "Nach Sonnenaufgang ist ENV-Tageslevel erreicht")

    s = calculate_light_sun_state(now_min=1260, **common)
    require(s["phase"] == "sunset" and s["level"] == 80, "Sonnenuntergang startet am Tageslevel")

    s = calculate_light_sun_state(now_min=1290, **common)
    require(11 < s["level"] < 80, "Sonnenuntergang dimmt nach unten")

    s = calculate_light_sun_state(now_min=1320, **common)
    require(s["on"] is False and s["level"] is None, "Nacht Start schaltet Licht AUS")

    cross = dict(
        day_start=1200,
        night_start=480,
        sunrise_duration=30,
        sunset_duration=30,
        min_level=11,
        target_level=60,
    )
    require(calculate_light_sun_state(now_min=30, **cross)["on"], "Tagesfenster über Mitternacht funktioniert")
    require(not calculate_light_sun_state(now_min=600, **cross)["on"], "Cross-midnight Nachtphase bleibt AUS")

    overlap = calculate_light_sun_state(
        now_min=390,
        day_start=360,
        night_start=420,
        sunrise_duration=60,
        sunset_duration=60,
        min_level=11,
        target_level=100,
    )
    require(11 <= overlap["level"] <= 100, "Überlappende Rampen bleiben begrenzt")

    control = (ROOT/"core/control.py").read_text(encoding="utf-8")
    config = (ROOT/"core/config.py").read_text(encoding="utf-8")
    settings = (ROOT/"templates/settings.html").read_text(encoding="utf-8")
    tents = (ROOT/"routes/tents.py").read_text(encoding="utf-8")

    require("calculate_light_sun_state" in control, "Control nutzt Sonnenverlauf-Modell")
    require('resolve_control_state(params, "off")' in control, "OFF bleibt bestehender Shelly-State")
    require('controller["level"] = int(sun["level"])' in control, "Rampe überschreibt nur Controller-Level")
    require('"LIGHT_SUN_ENABLED": 0' in config, "Feature ist standardmäßig AUS")
    require('id="LIGHT_SUN_ENABLED"' in settings, "Profilseite besitzt Aktiv-Schalter")
    require('id="LIGHT_SUNRISE_DURATION_MIN"' in settings, "Profilseite besitzt Sonnenaufgangsdauer")
    require('id="LIGHT_SUNSET_DURATION_MIN"' in settings, "Profilseite besitzt Sonnenuntergangsdauer")
    require('"light_sun_level": live.get("light_sun_level")' in tents, "API liefert aktiven Sonnenlevel")

    print("✅ Growstar 3.14.0 / LIGHT.SUN.1 vollständig geprüft")

if __name__ == "__main__":
    main()
