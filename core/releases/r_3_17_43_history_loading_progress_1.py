"""Growstar 3.17.43 / ENV.CHART.LOADING.1."""

RELEASE = {
    "version": "3.17.43",
    "date": "2026-10-12",
    "phase": "ENV.CHART.LOADING.1",
    "title": "Ladebalken für Verlaufsdiagramme",
    "summary": "Langsame Verlaufsabfragen zeigen einen sichtbaren Ladezustand und, wenn möglich, echten Downloadfortschritt.",
    "changes": [
        "Ein Ladebalken erscheint bei historischen Diagrammen und beim Vergleich, auch für sieben und 30 Tage.",
        "Bei bekannter unkomprimierter Antwortgröße zeigt er den Anteil tatsächlich empfangener Bytes.",
        "Ohne verlässliche Größe läuft der Balken ohne erfundene Prozentzahl.",
        "Beim Zeitraumwechsel werden ältere Abfragen abgebrochen und können die neue Anzeige nicht überschreiben.",
        "Statistikwerte lassen sich auch bei langen Zeiträumen ohne Argument-Limit berechnen.",
    ],
    "tests": [
        "node tests/regression/check_environment_single_chart_runtime.js",
        "python3 tests/regression/check_environment_single_chart.py",
        "python3 tests/regression/check_environment_compare.py",
        "python3 tests/regression/check_environment_tooltip.py",
        "python3 tests/regression/check_chart_stability.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
