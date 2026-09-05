#!/usr/bin/env python3
"""Regression für Growstar 3.16.18 / SHELL.4."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    css = (ROOT / "static" / "css" / "growstar-app-shell.css").read_text(
        encoding="utf-8"
    )
    shell_js = (ROOT / "static" / "js" / "growstar-app-shell.js").read_text(
        encoding="utf-8"
    )
    energy_routes = (ROOT / "routes" / "energy.py").read_text(encoding="utf-8")

    grow_index = base.index('<div class="growstar-nav-section-title">Grow Control</div>')
    plants_index = base.index(
        '<div class="growstar-nav-section-title">Pflanzenmanagement</div>'
    )
    energy_index = base.index('<div class="growstar-nav-section-title">Energie</div>')
    admin_index = base.index('<div class="growstar-nav-section-title">Administrator</div>')
    require(
        grow_index < plants_index < energy_index < admin_index,
        "Energie steht als dritte Hauptkategorie unter Pflanzenmanagement",
    )

    grow_section = base[grow_index:plants_index]
    require(
        "energie_page" not in grow_section
        and "growstar-energy-submenu" in base
        and "energie_page" in base
        and "energie_diagramme_page" in base
        and "energie_settings_page" in base,
        "Energie ist aus Grow Control gelöst und besitzt ein eigenes Untermenü",
    )

    require(
        "{% set growstar_energy_active" in base
        and "{% elif growstar_energy_active %}Energie" in base,
        "Energieseiten aktivieren ausschließlich den Energie-Kontext",
    )

    rows = re.findall(
        r'<div class="growstar-nav-group-row[^>]*>(.*?)</div>\s*'
        r'<div id="growstar-(?:grow|plants|energy)-submenu"',
        base,
        flags=re.DOTALL,
    )
    require(
        len(rows) == 3
        and all(
            row.index("growstar-nav-group-toggle")
            < row.index("growstar-nav-group-main")
            for row in rows
        ),
        "Alle aufklappbaren Hauptkategorien platzieren den Pfeil vor dem Modul-Link",
    )

    require(
        "grid-template-columns: 46px minmax(0, 1fr);" in css
        and "width: 42px;" in css
        and "min-height: 44px;" in css
        and "?v=3.16.18-shell4" in base,
        "Linker Pfeil, mobile Touchfläche und Cache-Buster sind aktiv",
    )

    require(
        "[data-growstar-nav-group-toggle]" in shell_js
        and "[data-growstar-nav-submenu]" in shell_js
        and "setGroupExpanded(group" in shell_js,
        "Die bestehende generische Aufklapplogik steuert auch die Energiekategorie",
    )

    require(
        '@app.route("/energie/diagramme")' in energy_routes
        and "def energie_diagramme_page()" in energy_routes,
        "Der neue Diagramm-Menüpunkt verweist auf die vorhandene Energieroute",
    )

    controlled_ids = re.findall(r'aria-controls="([^"]+)"', base)
    submenu_ids = re.findall(
        r'id="(growstar-(?:grow|plants|energy)-submenu)"',
        base,
    )
    require(
        set(controlled_ids).issuperset(submenu_ids)
        and len(submenu_ids) == len(set(submenu_ids)) == 3,
        "Pfeile und Untermenüs bleiben eindeutig und barrierearm verknüpft",
    )

    print("✅ Growstar 3.16.18 / SHELL.4 vollständig geprüft")


if __name__ == "__main__":
    main()
