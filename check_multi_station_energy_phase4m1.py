#!/usr/bin/env python3
"""Phase 4M.1 – separate große Energie-Diagrammseite.

Keine Hardware-/Netzwerkzugriffe. Geprüft werden Syntax und die Kopplung an
die vorhandenen Phase-4M-Read-APIs.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

try:
    from jinja2 import Environment
except ModuleNotFoundError:
    Environment = None


ROOT = Path(__file__).resolve().parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    routes=read("routes/energy.py")
    policy=read("auth/policy.py")
    overview=read("templates/energie.html")
    charts=read("templates/energie_diagramme.html")
    self_src=read("check_multi_station_energy_phase4m1.py")

    ast.parse(routes,filename="routes/energy.py")
    ast.parse(policy,filename="auth/policy.py")
    ast.parse(self_src,filename="check_multi_station_energy_phase4m1.py")
    print("✅ Python-Syntax Phase 4M.1")

    if Environment is not None:
        env=Environment()
        env.parse(overview)
        env.parse(charts)
        print("✅ Jinja-Syntax Phase 4M.1")

    require(
        '@app.route("/energie/diagramme")' in routes
        and 'render_template("energie_diagramme.html")' in routes,
        "Eigene Route /energie/diagramme vorhanden",
    )
    require(
        '"/energie/diagramme": require("grow.view")' in policy,
        "Diagrammseite nutzt dieselbe Leseberechtigung wie Energieübersicht",
    )
    require(
        'href="/energie/diagramme"' in overview,
        "Energieübersicht verlinkt die große Diagrammseite",
    )
    require(
        "/api/energy/history?range=" in charts
        and "/api/energy/overview" not in charts,
        "Diagrammseite verwendet ausschließlich die read-only History-API",
    )
    require(
        "fetch(" in charts
        and "/api/energy/reset" not in charts
        and "/api/energy/settings" not in charts,
        "Diagrammseite ist read-only",
    )
    require(
        "Gesamtleistung der Anlage" in charts
        and "Leistungsverlauf je Grow-Station" in charts,
        "Große Seite zeigt ausschließlich die großen Leistungsverläufe",
    )
    require(
        "Tagesauswertung" not in charts
        and "Geräteauswertung" not in charts
        and 'id="stationFilter"' not in charts,
        "Statistik- und Geräteauswertungen liegen nicht auf der Diagrammseite",
    )
    require(
        "Tagesauswertung" in overview
        and "Geräteauswertung" in overview
        and 'id="stationFilter"' in overview,
        "Tages- und Geräteauswertungen liegen auf der Energieübersicht",
    )
    require(
        'data-range="today"' in charts
        and 'data-range="24h"' in charts
        and 'data-range="7d"' in charts
        and 'data-range="30d"' in charts,
        "Große Seite behält alle vier History-Zeiträume",
    )
    require(
        "Chart.js" not in charts
        and "<svg" in charts,
        "Diagrammseite bleibt ohne externe Chart-Bibliothek",
    )

    print("✅ Phase 4M.1 separate Energie-Diagrammseite vollständig")


if __name__=="__main__":
    main()
