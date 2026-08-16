#!/usr/bin/env python3
"""Phase 4M.3 – klare Trennung von Energieauswertung und Diagrammen."""

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
    diagrams = read("templates/energie_diagramme.html")

    require(
        "Tagesauswertung" in overview
        and "Verbrauch heute nach Station" in overview
        and "Tagesmaximum nach Station" in overview,
        "Tagesauswertung liegt auf /energie",
    )
    require(
        "Geräteauswertung" in overview
        and "Aktuelle Geräteleistung" in overview
        and "Geräte-Maximum heute" in overview,
        "Geräteauswertung liegt auf /energie",
    )
    require(
        'id="stationFilter"' in overview,
        "Stationsfilter gehört zur Geräteauswertung auf /energie",
    )
    require(
        'href="/energie/diagramme">Diagramme</a>' in overview,
        "Übersichtsseite besitzt weiterhin den Diagramme-Button",
    )
    require(
        "/api/energy/history?range=" not in overview
        and "lineChart(" not in overview,
        "Übersichtsseite lädt keine Verlaufshistorie und zeichnet keine Liniencharts",
    )

    require(
        "Gesamtleistung der Anlage" in diagrams
        and "Leistungsverlauf je Grow-Station" in diagrams,
        "Diagrammseite besitzt die zwei großen Verlaufdiagramme",
    )
    require(
        "Tagesauswertung" not in diagrams
        and "Geräteauswertung" not in diagrams
        and "Verbrauch heute nach Station" not in diagrams
        and "Geräte-Maximum heute" not in diagrams,
        "Diagrammseite enthält keine Auswertungskarten",
    )
    require(
        "/api/energy/history?range=" in diagrams
        and "/api/energy/overview" not in diagrams,
        "Diagrammseite arbeitet ausschließlich mit der History-API",
    )
    require(
        'data-range="today"' in diagrams
        and 'data-range="24h"' in diagrams
        and 'data-range="7d"' in diagrams
        and 'data-range="30d"' in diagrams,
        "Alle vier Diagramm-Zeiträume bleiben erhalten",
    )

    if Environment is not None:
        env = Environment(loader=DictLoader({
            "base.html": (
                "<html><head>{% block head %}{% endblock %}</head>"
                "<body><main>{% block page %}{% endblock %}</main></body></html>"
            ),
            "energie.html": overview,
            "energie_diagramme.html": diagrams,
        }))
        rendered_overview = env.get_template("energie.html").render()
        rendered_diagrams = env.get_template("energie_diagramme.html").render()

        require(
            "Tagesauswertung" in rendered_overview
            and "Geräteauswertung" in rendered_overview,
            "Auswertungen rendern sichtbar auf der Übersichtsseite",
        )
        require(
            'id="controllerChart"' in rendered_diagrams
            and 'id="stationChart"' in rendered_diagrams,
            "Diagramme rendern sichtbar auf der separaten Seite",
        )
        print("✅ Jinja-Render-Test Phase 4M.3")

    print("✅ Phase 4M.3 Auswertung/Diagramm-Trennung vollständig")


if __name__ == "__main__":
    main()
