#!/usr/bin/env python3
"""The comparison overlays all selected series on one large canvas."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
chart = (ROOT / "templates/environment_history.html").read_text()


def require(condition, message):
    assert condition, message
    print("✅", message)


def main():
    require('let comparisonChart=null' in chart and 'comparisonCharts' not in chart,
            "Vergleich verwaltet genau eine Chart-Instanz")
    block = chart.split('function renderComparison(rows){', 1)[1].split('function updateStats(', 1)[0]
    require(block.count('new Chart(') == 1 and 'for(const [group,config]' not in block,
            "Alle aktivierten Kurven werden in einem Diagramm gezeichnet")
    require('yAxisID:`y_${group}`' in block and 'group:`temp`' not in block and
            'const groups=[...new Set(keys.map(key=>COMPARE_SERIES[key].group))]' in block,
            "Temperaturkurven teilen eine Achse und andere Einheiten behalten ihren Maßstab")
    require('const visible=groups.slice(0,2)' in block and
            'display:shown' in block and 'genaue Werte beim Antippen' in block,
            "Auf schmalen Bildschirmen bleiben höchstens zwei Achsen sichtbar")
    require('.page.wide{width:min(1450px,100%)}' in chart and
            '.compare-canvas{position:relative;height:min(68vh,680px);min-height:470px}' in chart and
            'class="compare-panel"' not in chart and 'height:250px' not in chart,
            "Diagramm nutzt mehr Breite und eine hohe Zeichenfläche ohne verschachtelte Karten")
    require('selectedSeries.add(key)' in chart and 'selectedSeries.delete(key)' in chart,
            "Jede Kurve bleibt einzeln ein- und ausschaltbar")
    print("✅ ENV.CHART.SINGLE.1 erfolgreich")


if __name__ == "__main__":
    main()
