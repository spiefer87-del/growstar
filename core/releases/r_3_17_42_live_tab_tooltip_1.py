"""Growstar 3.17.42 / ENV.CHART.LIVE.TAB.1."""

RELEASE = {
    "version": "3.17.42",
    "date": "2026-10-12",
    "phase": "ENV.CHART.LIVE.TAB.1",
    "title": "Live-Aufzeichnung als eigener Diagramm-Reiter",
    "summary": "Live-Steuerung und Live-Diagramm erscheinen nur im eigenen Live-Reiter.",
    "changes": [
        "Der Live-Reiter liegt direkt rechts neben Vergleich und besitzt eine eigene Stations-URL.",
        "Beim Öffnen werden Kurvenwahl und Startknopf gezeigt; die Aufzeichnung startet erst nach Antippen.",
        "Historische Zeiträume und Diagramme bleiben im Live-Reiter ausgeblendet.",
        "Live-Messwerte erscheinen erst nach Antippen der Kurve und verschwinden nach zwei Sekunden.",
        "Beim Verlassen des Live-Reiters wird eine laufende Abfrage beendet.",
    ],
    "tests": [
        "node tests/regression/check_environment_single_chart_runtime.js",
        "python3 tests/regression/check_environment_tooltip.py",
        "python3 tests/regression/check_environment_compare.py",
        "python3 tests/regression/check_environment_single_chart.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
