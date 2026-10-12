"""Growstar 3.17.41 / ENV.CHART.LIVE.SEPARATE.1."""

RELEASE = {
    "version": "3.17.41",
    "date": "2026-10-12",
    "phase": "ENV.CHART.LIVE.SEPARATE.1",
    "title": "Eigenes Live-Diagramm und längere Verlaufszeiträume",
    "summary": "Live-Messungen laufen in einer eigenen Ansicht; die Historie bietet 48 Stunden und 30 Tage.",
    "changes": [
        "Das Live-Diagramm startet manuell im Vergleich und zeigt eine mitlaufende Fünf-Minuten-Zeitachse.",
        "Der Vergleich der gespeicherten Messungen bleibt unabhängig von der Live-Aufzeichnung.",
        "Nach dem Stoppen bleibt die Live-Kurve bis zum Verlassen der Seite sichtbar; ein Neustart beginnt neu.",
        "48 Stunden und 30 Tage sind für alle Verlaufsdiagramme und den Vergleich auswählbar.",
        "Veraltete Sensorwerte und Verbindungsfehler ergeben im Live-Diagramm Messlücken.",
    ],
    "tests": [
        "node tests/regression/check_environment_single_chart_runtime.js",
        "python3 tests/regression/check_environment_single_chart.py",
        "python3 tests/regression/check_environment_compare.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
