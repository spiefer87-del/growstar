#!/usr/bin/env python3

from pathlib import Path

try:
    from jinja2 import DictLoader, Environment
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
    overview = read("templates/energie.html")
    charts = read("templates/energie_diagramme.html")

    require(
        "{% block page %}" in charts and "{% block content %}" not in charts,
        "Diagrammseite verwendet den Growstar-Inhaltsblock 'page'",
    )

    if Environment is not None:
        env = Environment(loader=DictLoader({
            "base.html": (
                "<html><head>{% block head %}{% endblock %}</head>"
                "<body><main>{% block page %}{% endblock %}</main></body></html>"
            ),
            "energie.html": overview,
            "energie_diagramme.html": charts,
        }))

        rendered = env.get_template("energie_diagramme.html").render()
        require(
            "Energie-Diagramme" in rendered
            and 'id="controllerChart"' in rendered
            and 'id="stationChart"' in rendered,
            "Diagrammseite rendert sichtbar gegen base.html statt leer zu bleiben",
        )

        rendered_overview = env.get_template("energie.html").render()
        require(
            "Energie & Statistik" in rendered_overview,
            "Energieübersicht rendert weiterhin korrekt",
        )
        print("✅ Jinja-Render-Test Phase 4M.2")

    require(
        'href="/energie/diagramme">Diagramme</a>' in overview,
        "Ein einzelner Diagramme-Button befindet sich im Seiteninhalt",
    )
    require(
        "Diagramme groß" not in overview,
        "Oberer 'Diagramme groß'-Link ist entfernt",
    )
    require(
        "controllerPowerChart" not in overview
        and "stationPowerChart" not in overview
        and "stationTodayBars" not in overview
        and "devicePowerBars" not in overview,
        "Kleine Diagramme sind aus der Energieübersicht entfernt",
    )
    require(
        "/api/energy/history?range=" not in overview
        and "loadHistory" not in overview,
        "Energieübersicht lädt keine History-Daten mehr",
    )
    require(
        "/api/energy/overview" in overview,
        "Kennzahlen und Stationsdaten der Energieübersicht bleiben aktiv",
    )
    require(
        "/api/energy/overview" in charts
        and "/api/energy/history?range=" in charts,
        "Große Diagrammseite nutzt weiterhin beide Phase-4M-Read-APIs",
    )
    require(
        'data-range="today"' in charts
        and 'data-range="24h"' in charts
        and 'data-range="7d"' in charts
        and 'data-range="30d"' in charts,
        "Alle vier Diagramm-Zeiträume bleiben vorhanden",
    )

    print("✅ Phase 4M.2 vollständig")


if __name__ == "__main__":
    main()
