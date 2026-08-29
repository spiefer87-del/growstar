"""Growstar 3.14.3 / DASH.PPFD.CARD.1 release metadata."""

RELEASE = {
    "version": "3.14.3",
    "date": "2026-08-29",
    "phase": "DASH.PPFD.CARD.1",
    "title": "Helligkeits-Kachel für PPFD aufräumen",
    "summary": "Die Helligkeits-Kachel zeigt PPFD kompakter und ohne Sensorname oder Zelt-Detail-Hinweis.",
    "changes": (
        "PPFD-Messwert bleibt groß und zentral.",
        "µmol/m²/s steht kleiner unter dem Messwert.",
        "Sensorname wird aus der Dashboard-Kachel entfernt.",
        "Zelt-Detail-folgt-Markierung wird entfernt.",
        "Kachelstruktur wird für eine kommende Diagrammseite vorbereitet.",
        "Keine Änderung an PPFD-Erfassung oder Lichtregelung.",
    ),
    "tests": (
        "python3 tests/regression/check_dashboard_ppfd_card.py",
        "python3 tests/regression/check_spiderfarmer_ppfd_dashboard.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
