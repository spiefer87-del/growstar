#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)

def main():
    settings = (ROOT/"templates/settings.html").read_text(encoding="utf-8")
    tents = (ROOT/"routes/tents.py").read_text(encoding="utf-8")
    control = (ROOT/"core/control.py").read_text(encoding="utf-8")

    require('id="light-sun-card"' in settings, "Sonnenverlauf-Karte ist adressierbar")
    require(".card.feature-unavailable{" in settings, "Karte besitzt Ausgrau-CSS")
    require("function applyLightSunAvailability(payload){" in settings, "Frontend-Verfügbarkeitsfunktion ist vorhanden")
    require('card.classList.toggle(' in settings and '"feature-unavailable"' in settings, "Frontend schaltet Ausgrau-Zustand")
    require("input.disabled = !lightSunAvailable" in settings, "Sonnenverlauf-Eingaben werden deaktiviert")
    require("button.disabled = !lightSunAvailable" in settings, "Plus/Minus-Tasten werden deaktiviert")
    require('id="light-sun-controller-note"' in settings, "Hinweisfeld für fehlenden Controller ist vorhanden")
    require("<strong>Nicht verfügbar:</strong>" in settings, "Hinweis erklärt die Nichtverfügbarkeit")
    require("lightSunAvailable && !!c.LIGHT_SUN_ENABLED" in settings, "Persistiertes Aktiv-Flag kann UI ohne Controller nicht einschalten")
    require("lightSunAvailable &&" in settings and 'el("LIGHT_SUN_ENABLED").checked' in settings, "Save-Payload kann ohne Controller nicht Aktiv=1 senden")
    require("def _light_sun_availability(runtime):" in tents, "Backend-Verfügbarkeitsprüfung bleibt erhalten")
    require("light_sun_controller_required" in tents, "Backend-POST-Guard bleibt erhalten")
    require('light_sun_phase"] = "controller_required"' in control, "Runtime-Fail-safe bleibt erhalten")

    print("✅ Growstar 3.14.2 / LIGHT.SUN.GUARD.2 vollständig geprüft")

if __name__ == "__main__":
    main()
