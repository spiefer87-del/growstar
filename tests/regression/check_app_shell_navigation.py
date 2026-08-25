#!/usr/bin/env python3
"""Growstar 3.13.2 / Shell.3 navigation architecture guard."""
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[2]

def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)

def main():
    base = (ROOT / "templates/base.html").read_text(encoding="utf-8")
    css = (ROOT / "static/css/growstar-app-shell.css").read_text(encoding="utf-8")
    js = (ROOT / "static/js/growstar-app-shell.js").read_text(encoding="utf-8")

    require("?v=3.13.2-shell3" in base, "Shell.3 Cache-Buster aktiv")
    require(base.count("data-growstar-nav-group") >= 2, "Grow Control und Pflanzenmanagement sind klappbare Module")
    require('id="growstar-grow-submenu"' in base, "Grow-Control-Untermenü vorhanden")
    require('id="growstar-plants-submenu"' in base, "Pflanzen-Untermenü vorhanden")
    require("growstar-nav-submenu-label\">Technik" in base, "Technik ist innerhalb von Grow Control einsortiert")

    grow_targets = (
        "grow_control_dashboard", "grow_control_live", "grow_control_sensors_dashboard",
        "devices", "grow_control_connections", "spiderfarmer_system_page", "energie_page",
        "diagrams_page", "grow_control_watchdog", "grow_control_setup", "system_page",
    )
    for endpoint in grow_targets:
        require(f"url_for('{endpoint}')" in base, f"Grow-Control-Ziel {endpoint} vorhanden")

    admin_targets = ("admin_index", "admin_users", "admin_roles", "admin_audit")
    for endpoint in admin_targets:
        require(f"url_for('{endpoint}')" in base, f"Administrator-Ziel {endpoint} vorhanden")

    require("has_any_permission('users.view', 'users.manage')" in base, "Benutzer-Menü respektiert Berechtigungen")
    require("has_any_permission('roles.view', 'roles.manage')" in base, "Rollen-Menü respektiert Berechtigungen")
    require("has_permission('audit.view')" in base, "Audit-Menü respektiert Berechtigung")
    require("setGroupExpanded" in js, "bewährte Klappgruppen-Logik bleibt aktiv")
    require("fetch(" not in js, "Shell führt keine API-/Regelungszugriffe aus")
    require("growstar-nav-submenu-label" in css, "Technik-Zwischenüberschrift ist gestaltet")
    require("device-setpoint-stepper.js" in base and "growstar-feedback.js" in base, "bestehende UI-Helfer bleiben erhalten")
    print("✅ Growstar 3.13.2 / SHELL.3 vollständig geprüft")

if __name__ == "__main__":
    main()
