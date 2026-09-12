"""Growstar 3.17.10 / INTELLIGENCE.TEMPLATE-FIX.1 release metadata."""

RELEASE = {
    "version": "3.17.10",
    "date": "2026-09-12",
    "phase": "INTELLIGENCE.TEMPLATE-FIX.1",
    "title": "Grow-Intelligence-Ansicht repariert",
    "summary": (
        "Die Erkenntniskarten werden wieder korrekt aus der übergebenen "
        "Liste gerendert."
    ),
    "changes": [
        "Der Jinja-Zugriff auf die Erkenntnisliste ist eindeutig und kollidiert nicht mehr mit der Dictionary-Methode items().",
        "Der Regressionstest schützt die Grow-Intelligence-Seite vor demselben Renderingfehler.",
    ],
    "tests": [
        "python3 tests/regression/check_grow_intelligence_insights.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
