#!/usr/bin/env python3
"""Regression für Grow-Control-Schnellmenü und Diagrammübersicht."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from auth.policy import permission_requirement


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    base = (ROOT / "templates/base.html").read_text(encoding="utf-8")
    routes = (ROOT / "routes/dashboard.py").read_text(encoding="utf-8")
    overview = (ROOT / "templates/grow_control_diagrams.html").read_text(encoding="utf-8")
    management = (ROOT / "templates/diagrams.html").read_text(encoding="utf-8")
    history = (ROOT / "templates/environment_history.html").read_text(encoding="utf-8")
    dashboard = (ROOT / "templates/grow_control_dashboard.html").read_text(encoding="utf-8")

    grow_menu = base[base.index('id="growstar-grow-submenu"'):base.index('id="growstar-hardware-submenu"')]
    require(
        "Profile &amp; Darstellung" in grow_menu
        and "url_for('grow_control_profiles')" in grow_menu
        and "url_for('grow_control_design')" in grow_menu,
        "Profile und Dashboard-Design sind direkt im Grow-Control-Schnellmenü erreichbar",
    )
    require(
        "Grow Intelligence" in grow_menu
        and "url_for('grow_control_events')" in grow_menu,
        "Grow Intelligence ist direkt im Grow-Control-Schnellmenü erreichbar",
    )
    require(
        "Diagrammübersicht" in grow_menu
        and "url_for('grow_control_diagram_temperature')" in grow_menu
        and "url_for('grow_control_diagram_humidity')" in grow_menu
        and "url_for('grow_control_diagram_vpd')" in grow_menu
        and "Diagrammdaten" in grow_menu,
        "Das Schnellmenü trennt Diagrammansichten von Import, Export und Reset",
    )
    require(
        '@app.route("/grow-control/diagrams")' in routes
        and "grow_control_diagrams.html" in routes
        and "tents=tent_manager.list_tents()" in routes
        and "default_tent_id=tent_manager.default_tent_id()" in routes,
        "Die neue Diagrammübersicht erhält alle Stationen und die Hauptstation",
    )
    for endpoint in (
        "grow_control_tent_temperature", "grow_control_tent_humidity",
        "grow_control_tent_vpd", "grow_control_tent_ppfd",
    ):
        require(f"url_for('{endpoint}'" in overview, f"Diagrammübersicht verlinkt {endpoint}")
    require(
        "Import, Export &amp; Reset" in overview
        and "Diagrammdaten verwalten" in management
        and "grow_control_diagrams_dashboard" in management
        and "grow_control_diagrams_dashboard" in history,
        "Diagrammverwaltung und Einzelverläufe führen zurück zur Übersicht",
    )
    require(
        "url_for('grow_control_profiles')" in dashboard
        and "url_for('grow_control_design')" in dashboard
        and "url_for('grow_control_events')" in dashboard
        and "url_for('grow_control_diagrams_dashboard')" in dashboard,
        "Grow-Control-Dashboard bietet Profile, Design, Intelligence und Diagramme als Schnellzugriff",
    )
    require(
        permission_requirement("/grow-control/profiles", "GET").permissions == ("settings.view",)
        and permission_requirement("/grow-control/design", "GET").permissions == ("settings.view",)
        and permission_requirement("/grow-control/events", "GET").permissions == ("grow.view",)
        and permission_requirement("/grow-control/diagrams", "GET").permissions == ("grow.view",),
        "Schnellzugriffe behalten getrennte Anzeige- und Einstellungsrechte",
    )

    print("✅ Grow-Control-Schnellmenü und Diagrammübersicht vollständig geprüft")


if __name__ == "__main__":
    main()
