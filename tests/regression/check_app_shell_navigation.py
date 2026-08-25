#!/usr/bin/env python3
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[2]

def require(ok, msg):
    if not ok: raise AssertionError(msg)
    print("✅", msg)

def main():
    base=(ROOT/"templates/base.html").read_text(encoding="utf-8")
    css=(ROOT/"static/css/growstar-app-shell.css").read_text(encoding="utf-8")
    js=(ROOT/"static/js/growstar-app-shell.js").read_text(encoding="utf-8")
    live=(ROOT/"templates/grow_control.html").read_text(encoding="utf-8")
    pnav=(ROOT/"templates/plants/_nav.html").read_text(encoding="utf-8")
    require("html { font-size: 11px; }" in live, "Live-Seite besitzt weiterhin ihre eigene mobile Schriftbasis")
    require(not re.search(r"[0-9.]rem", css), "Globale Shell ist vollständig von rem-Skalierung entkoppelt")
    require("data-growstar-nav-group-toggle" in base and "data-growstar-nav-submenu" in base, "Pflanzenmanagement besitzt ein Klappmenü")
    require("setGroupExpanded" in js, "Klappmenü wird im Shell-JavaScript verwaltet")
    for ep in ("plant_management_dashboard","plant_list","plant_timeline","cultivar_list","genetics_dashboard","propagation_dashboard_page","batch_list","plant_journal"):
        require(f"url_for('{ep}')" in base, f"Drawer enthält {ep}")
        require(ep in pnav, f"{ep} entspricht der bestehenden Pflanzen-Navigation")
    require("?v=3.13.1-shell2" in base, "Shell.2 Cache-Buster aktiv")
    require("device-setpoint-stepper.js" in base and "growstar-feedback.js" in base, "Bestehende UI-Helfer bleiben erhalten")
    require("fetch(" not in js, "Shell führt keine API-/Regelungszugriffe aus")
    print("✅ Growstar 3.13.1 / Shell.2 vollständig geprüft")

if __name__ == "__main__": main()
