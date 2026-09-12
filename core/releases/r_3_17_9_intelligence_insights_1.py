"""Growstar 3.17.9 / INTELLIGENCE.INSIGHTS.1 release metadata."""

RELEASE = {
    "version": "3.17.9",
    "date": "2026-09-12",
    "phase": "INTELLIGENCE.INSIGHTS.1",
    "title": "Nachvollziehbare Stations-Erkenntnisse",
    "summary": (
        "Grow Intelligence verdichtet Timeline-Ereignisse erstmals zu "
        "stationsbezogenen, belegbaren Hinweisen."
    ),
    "changes": [
        "Offene Watchdog-Vorgänge bleiben sichtbar, bis eine passende Entwarnung erfasst wurde.",
        "Entwarnungen im gewählten Zeitraum werden zu einer kompakten Erfolgsmeldung zusammengefasst.",
        "Zeitnahe Klima- und Gerätealarme derselben Station werden vorsichtig als zeitlicher Zusammenhang markiert.",
        "Das zuletzt erkannte Tag-/Nacht- oder Grow-Profil wird je Station zusammengefasst.",
        "Eine länger zurückliegende Pflanzendokumentation kann als Hinweis erscheinen.",
        "Jede Erkenntnis nennt ihre zugrunde liegenden Timeline-Ereignisnummern.",
        "Die Auswertung bleibt read-only, stationsgetrennt und verändert keine Regelparameter.",
    ],
    "tests": [
        "python3 tests/regression/check_grow_intelligence_insights.py",
        "python3 tests/regression/check_grow_intelligence_integration.py",
        "python3 tests/regression/check_grow_intelligence_events.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
