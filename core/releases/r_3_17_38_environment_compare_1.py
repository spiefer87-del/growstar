"""Growstar 3.17.38 / ENV.CHART.COMPARE.1."""

RELEASE = {
    "version": "3.17.38",
    "date": "2026-10-02",
    "phase": "ENV.CHART.COMPARE.1",
    "title": "Messwerte auf gemeinsamer Zeitachse vergleichen",
    "summary": "Innen-, Wasser- und Außentemperatur überlagern; weitere Einheiten getrennt einblenden.",
    "changes": [
        "Außentemperatur und Außenfeuchte werden künftig stationsbezogen historisiert.",
        "Aufklappbare Kurvenauswahl mit sieben Messreihen und gespeicherter Auswahl pro Station.",
        "Temperaturkurven teilen sich eine Celsius-Achse; andere Einheiten besitzen eigene Bereiche.",
        "Die Wassertemperatur-Kachel führt direkt in den Vergleich.",
        "Frühere Messungen bleiben erhalten; fehlende Außenwerte werden nicht erfunden.",
    ],
    "tests": [
        "python3 tests/regression/check_environment_compare.py",
        "python3 tests/regression/check_history_binding_fix.py",
        "python3 tests/regression/check_combined_climate_chart.py",
        "python3 tests/regression/check_chart_station_switch_layout.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
