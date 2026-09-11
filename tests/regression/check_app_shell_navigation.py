#!/usr/bin/env python3
"""Growstar App-Shell navigation architecture guard."""
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
    require(base.count("data-growstar-nav-group") >= 4, "Grow Control, Hardware, Pflanzen und Medien sind klappbare Module")
    require('id="growstar-grow-submenu"' in base, "Grow-Control-Untermenü vorhanden")
    require('id="growstar-hardware-submenu"' in base, "Hardware-Untermenü vorhanden")
    require('id="growstar-plants-submenu"' in base, "Pflanzen-Untermenü vorhanden")
    require('id="growstar-media-submenu"' in base, "Medien-Untermenü vorhanden")

    grow_targets = (
        "grow_control_dashboard", "grow_control_live", "grow_control_profiles",
        "grow_control_design", "grow_control_diagrams_dashboard",
        "grow_control_diagram_temperature", "grow_control_diagram_humidity",
        "grow_control_diagram_vpd", "diagrams_page",
    )
    grow_menu = base[base.index('id="growstar-grow-submenu"'):base.index('id="growstar-hardware-submenu"')]
    for endpoint in grow_targets:
        require(f"url_for('{endpoint}')" in grow_menu, f"Grow-Control-Ziel {endpoint} vorhanden")

    hardware_targets = (
        "hardware_management_dashboard", "devices", "grow_control_sensors_dashboard",
        "grow_control_connections", "spiderfarmer_system_page", "grow_control_watchdog",
        "grow_control_setup", "system_network_page", "system_page",
    )
    hardware_menu = base[base.index('id="growstar-hardware-submenu"'):base.index('growstar-nav-section-plants')]
    for endpoint in hardware_targets:
        require(f"url_for('{endpoint}')" in hardware_menu, f"Hardware-Ziel {endpoint} vorhanden")
    require("devices" not in grow_menu and "grow_control_setup" not in grow_menu, "Hardware und Setup sind aus Grow Control entfernt")

    admin_targets = ("admin_index", "admin_users", "admin_roles", "admin_audit")
    for endpoint in admin_targets:
        require(f"url_for('{endpoint}')" in base, f"Administrator-Ziel {endpoint} vorhanden")

    require("has_any_permission('users.view', 'users.manage')" in base, "Benutzer-Menü respektiert Berechtigungen")
    require("has_any_permission('roles.view', 'roles.manage')" in base, "Rollen-Menü respektiert Berechtigungen")
    require("has_permission('audit.view')" in base, "Audit-Menü respektiert Berechtigung")
    require("setGroupExpanded" in js, "bewährte Klappgruppen-Logik bleibt aktiv")
    require("fetch(" not in js, "Shell führt keine API-/Regelungszugriffe aus")
    require("growstar-nav-submenu" in css, "Klappbare Untermenüs sind gestaltet")
    require("device-setpoint-stepper.js" in base and "growstar-feedback.js" in base, "bestehende UI-Helfer bleiben erhalten")
    print("✅ Growstar App-Shell mit eigenständigem Hardware-Modul vollständig geprüft")

if __name__ == "__main__":
    main()
