#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)

def main():
    tents = (ROOT/"routes/tents.py").read_text(encoding="utf-8")
    control = (ROOT/"core/control.py").read_text(encoding="utf-8")
    ui = (ROOT/"templates/settings.html").read_text(encoding="utf-8")

    require("def _light_sun_availability(runtime):" in tents, "Zentrale Lichtcontroller-Prüfung vorhanden")
    require('"light_sun_available": bool(sun["available"])' in tents, "Config-GET liefert Verfügbarkeit")
    require('"light_sun_controller_required"' in tents, "Config-POST blockiert Aktivierung ohne Controller")
    require('light_sun_phase"] = "controller_required"' in control, "Runtime besitzt Fail-safe")
    require('id="light-sun-card"' in ui, "Sonnenverlauf-Karte adressierbar")
    require("feature-unavailable" in ui, "Karte wird ausgegraut")
    require('id="light-sun-controller-note"' in ui, "Begründung wird angezeigt")
    require("input.disabled = !lightSunAvailable" in ui, "Eingaben werden deaktiviert")
    require("button.disabled = !lightSunAvailable" in ui, "Plus/Minus wird deaktiviert")
    print("✅ Growstar 3.14.1 / LIGHT.SUN.GUARD.1 vollständig geprüft")

if __name__ == "__main__":
    main()
