"""Growstar 3.17.39 / ENV.CHART.SINGLE.1."""

RELEASE = {
    "version": "3.17.39",
    "date": "2026-10-02",
    "phase": "ENV.CHART.SINGLE.1",
    "title": "Alle Vergleichskurven in einem großen Diagramm",
    "summary": "Ein gemeinsames Overlay ersetzt die separaten kleinen Vergleichsdiagramme.",
    "changes": [
        "Alle ausgewählten Messreihen werden in einer einzigen großen Chart gezeichnet.",
        "Zelt-, Wasser- und Außentemperatur nutzen gemeinsam die Celsius-Skala.",
        "Andere Einheiten besitzen eigene Skalen; auf Mobilgeräten bleiben maximal zwei Achsen sichtbar.",
        "Die exakten Werte samt Einheit stehen beim Antippen der Kurven.",
        "Die Vergleichsansicht nutzt mehr Breite und Höhe.",
    ],
    "tests": [
        "python3 tests/regression/check_environment_single_chart.py",
        "node tests/regression/check_environment_single_chart_runtime.js",
        "python3 tests/regression/check_environment_compare.py",
        "python3 tests/regression/check_combined_climate_chart.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
