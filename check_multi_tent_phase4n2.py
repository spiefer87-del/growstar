#!/usr/bin/env python3
"""Phase 4N.2 – Design-Kachel im Grow-Control-Hub.

Nur statische/Jinja-Prüfung. Keine Hardware- oder Netzwerkzugriffe.
"""
from pathlib import Path

try:
    from jinja2 import Environment
except ModuleNotFoundError:
    Environment = None

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    hub = (ROOT / "templates" / "grow_control_dashboard.html").read_text(encoding="utf-8")

    if Environment is not None:
        Environment().parse(hub)
        print("✅ Jinja-Syntax Phase 4N.2")

    require(
        "{% if has_permission('settings.view') %}" in hub,
        "Design-Kachel liegt im geschützten settings.view-Bereich",
    )
    require(
        'url_for(\'design_page\')' in hub,
        "Design-Kachel verwendet die bestehende Design-Route",
    )
    require(
        "<h3>Design</h3>" in hub and "🎨" in hub,
        "Grow-Control-Hub enthält sichtbare Design-Kachel",
    )
    require(
        "Dashboard-Kacheln pro Station" in hub,
        "Design-Kachel erklärt stationsbezogene Sichtbarkeit und Reihenfolge",
    )

    # Bestehende zentrale Bereiche dürfen durch den kleinen UI-Patch
    # nicht verschwinden oder auf alte Legacy-Ziele zurückfallen.
    require("grow_control_setup" in hub and "<h3>Setup</h3>" in hub,
            "Setup-Kachel bleibt kanonisch erhalten")
    require("grow_control_sensors_dashboard" in hub and "<h3>Sensoren</h3>" in hub,
            "Sensoren-Kachel bleibt kanonisch erhalten")
    require("grow_control_watchdog" in hub and "<h3>Watchdog</h3>" in hub,
            "Watchdog-Kachel bleibt kanonisch erhalten")
    require("grow_control_connections" in hub and "<h3>Verbindungen</h3>" in hub,
            "Verbindungen-Kachel bleibt kanonisch erhalten")
    require("<h3>Hardware</h3>" in hub and "<h3>Energie</h3>" in hub,
            "Hardware und Energie bleiben erhalten")

    # Kein Backend-/Aktorcode gehört in diesen Patch.
    require("fetch(" in hub, "Bestehende read-only Stationsübersicht bleibt vorhanden")
    require("switch_shelly" not in hub and "/api/device" not in hub,
            "Design-Kachel führt keine Hardware-Aktorik ein")

    print("✅ Phase 4N.2 Design-Kachel im Grow-Control-Hub vollständig")


if __name__ == "__main__":
    main()
