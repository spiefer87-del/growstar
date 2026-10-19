"""Growstar 3.17.44 / ENV.CHART.CUSTOM.RANGE.1."""

RELEASE = {
    "version": "3.17.44",
    "date": "2026-10-19",
    "phase": "ENV.CHART.CUSTOM.RANGE.1",
    "title": "Kalender für eigene Diagrammzeiträume",
    "summary": "Verlaufsdiagramme und Vergleich können einen frei gewählten Start- und Endtag auswerten.",
    "changes": [
        "Zusätzlicher Kalender-Reiter in der Zeitraumleiste öffnet einen kompakten Dialog.",
        "Start- und Enddatum sind eingeschlossen und werden in lokaler Zeit interpretiert.",
        "Die gewählte Spanne gilt für alle historischen Metriken und den Vergleich der Station.",
        "Server und Dialog prüfen Reihenfolge, Zukunftsdatum und die Grenze von 366 Tagen.",
        "Ladebalken und Statistikwerte funktionieren auch für selbst gewählte Zeiträume.",
    ],
    "tests": [
        "node tests/regression/check_environment_single_chart_runtime.js",
        "python3 tests/regression/check_environment_compare.py",
        "python3 tests/regression/check_environment_single_chart.py",
        "python3 tests/regression/check_environment_tooltip.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
