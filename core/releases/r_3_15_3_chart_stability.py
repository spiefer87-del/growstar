"""Growstar 3.15.3 / ENV.CHARTS.STABILITY release metadata."""

RELEASE = {
    "version": "3.15.3",
    "date": "2026-08-29",
    "phase": "ENV.CHARTS.STABILITY",
    "title": "Diagramm-Zeitskala stabilisieren und PPFD-Test reparieren",
    "summary": "Alle Zeiträume nutzen dieselbe Chart.js-Time-Scale; API-, Leer- und Renderfehler werden getrennt dargestellt.",
    "changes": (
        "1h wechselt nicht mehr auf eine andere Chart.js-Skala.",
        "1h, 6h, 24h und 7d verwenden einheitlich die Time-Scale.",
        "API-Fehler werden von Chart-Renderfehlern getrennt.",
        "Leere Zeiträume werden nicht mehr als technischer Fehler angezeigt.",
        "PPFD-Dashboard-Regressionstest ist nicht mehr von JS-Zeilenumbrüchen abhängig.",
        "Stationswechsel bleibt vollständig erhalten.",
    ),
    "tests": (
        "python3 tests/regression/check_chart_stability.py",
        "python3 tests/regression/check_environment_charts.py",
        "python3 tests/regression/check_spiderfarmer_ppfd_dashboard.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
