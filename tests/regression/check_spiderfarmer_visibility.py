#!/usr/bin/env python3
"""Regression for Spider Farmer SF.3C.1 Grow-Control visibility."""

from __future__ import annotations

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
    grow_control_path = ROOT / "templates/grow_control_dashboard.html"
    main_dashboard_path = ROOT / "templates/dashboard.html"
    route_path = ROOT / "routes/dashboard.py"

    require(
        grow_control_path.is_file(),
        "Grow-Control-Dashboard vorhanden",
    )

    require(
        route_path.is_file(),
        "Dashboard-Routenmodul vorhanden",
    )

    grow_control = grow_control_path.read_text(encoding="utf-8")
    main_dashboard = (
        main_dashboard_path.read_text(encoding="utf-8")
        if main_dashboard_path.is_file()
        else ""
    )
    routes = route_path.read_text(encoding="utf-8")

    require(
        "Spider Farmer" in grow_control,
        "Spider Farmer ist im Grow-Control-Dashboard sichtbar",
    )

    require(
        "url_for('spiderfarmer_system_page')" in grow_control,
        "Grow-Control-Kachel verlinkt auf die native Spider-Farmer-Seite",
    )

    require(
        "SF · READ-ONLY" in grow_control,
        "Grow-Control-Kachel kennzeichnet den aktuellen read-only Stand",
    )

    require(
        "{% if has_permission('hardware.view') %}" in grow_control,
        "Spider-Farmer-Kachel nutzt den bestehenden Hardware-Berechtigungsblock",
    )

    require(
        "url_for('spiderfarmer_system_page')" not in main_dashboard,
        "Hauptdashboard erhält bewusst keine Spider-Farmer-Kachel",
    )

    require(
        '@app.get("/system/spiderfarmer")' in routes,
        "Zielroute /system/spiderfarmer bleibt registriert",
    )

    require(
        '@app.get("/api/spiderfarmer/controllers")' in routes,
        "Read-only Controller-API bleibt registriert",
    )

    for forbidden in (
        "@app.post(\"/api/spiderfarmer",
        "@app.put(\"/api/spiderfarmer",
        "@app.patch(\"/api/spiderfarmer",
        "@app.delete(\"/api/spiderfarmer",
    ):
        require(
            forbidden not in routes,
            f"SF.3C.1 führt keinen neuen Schreibpfad ein: {forbidden}",
        )

    print(
        "✅ Spider Farmer SF.3C.1 Grow-Control-Sichtbarkeit vollständig erfolgreich"
    )


if __name__ == "__main__":
    main()
