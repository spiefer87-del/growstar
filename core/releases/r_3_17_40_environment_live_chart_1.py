"""Growstar 3.17.40 / ENV.CHART.LIVE.1."""

RELEASE = {
    "version": "3.17.40",
    "date": "2026-10-02",
    "phase": "ENV.CHART.LIVE.1",
    "title": "Zuschaltbare Live-Kurven im Stationsvergleich",
    "summary": "Der Vergleich zeichnet neue frische Stationswerte alle fünf Sekunden weiter.",
    "changes": [
        "Live-Aufzeichnung startet ausschließlich über einen Schalter im Vergleich und ist zunächst aus.",
        "Zelt-, Wasser-, Außen-, VPD- und Lichtwerte werden in derselben Chart ergänzt.",
        "Sensor-Frische und Loop-Heartbeat verhindern erfundene Messpunkte; Ausfälle erzeugen Lücken.",
        "Wechsel des Reiters, Ausschalten und Verlassen der Seite stoppen die Live-Abfrage.",
        "Die bestehende dauerhafte Historie und ihr Schreibintervall bleiben erhalten.",
    ],
    "tests": [
        "node tests/regression/check_environment_single_chart_runtime.js",
        "python3 tests/regression/check_environment_single_chart.py",
        "python3 tests/regression/check_environment_compare.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
