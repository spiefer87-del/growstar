"""Growstar 3.17.34 / ENV.CLIMATE.COMBINED.1 release metadata."""

RELEASE = {
    "version": "3.17.34",
    "date": "2026-10-01",
    "phase": "ENV.CLIMATE.COMBINED.1",
    "title": "VPD-Chart in den Diagrammreitern und gemeinsamer Klimaverlauf",
    "summary": "VPD-Chart in der Diagrammnavigation; Temperatur und Feuchte wahlweise gemeinsam anzeigen.",
    "changes": [
        "VPD-Chart ist als eigener Reiter mit den übrigen Umgebungsdiagrammen verbunden.",
        "Der kleine grüne VPD-Chart-Button in der Zeltkachel wurde entfernt.",
        "Temperatur- und Feuchteseiten bieten eine zuschaltbare zweite Kurve.",
        "Beide Größen verwenden dieselben historischen Zeitpunkte mit eigener °C- und %-Skala.",
        "Der vorhandene Sollwert-Schalter steuert weiterhin nur den Sollwert der gewählten Messgröße.",
    ],
    "tests": [
        "python3 tests/regression/check_combined_climate_chart.py",
        "python3 tests/regression/check_environment_charts.py",
        "python3 tests/regression/check_chart_stability.py",
        "python3 tests/regression/check_vpd_chart.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
