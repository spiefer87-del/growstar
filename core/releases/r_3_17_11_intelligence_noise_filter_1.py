"""Growstar 3.17.11 / INTELLIGENCE.NOISE-FILTER.1 release metadata."""

RELEASE = {
    "version": "3.17.11",
    "date": "2026-09-12",
    "phase": "INTELLIGENCE.NOISE-FILTER.1",
    "title": "Ruhige Profil-Timeline",
    "summary": (
        "App-Neustarts erzeugen keine Profilereignisse mehr und bereits "
        "gespeicherte Start-Erkennungen werden ohne Datenverlust ausgeblendet."
    ),
    "changes": [
        "Die erste Tag-/Nacht-Erkennung nach Prozessstart initialisiert nur den Laufzeitstatus.",
        "Nur echte Wechsel zwischen Tag- und Nachtfenster erzeugen weiterhin Timeline-Ereignisse.",
        "Manuell angewendete Grow-Profile bleiben vollständig sichtbar.",
        "Historische Start-Erkennungen werden in Timeline, Kennzahlen und Erkenntnissen standardmäßig gefiltert.",
        "Der Filter löscht keine gespeicherten Ereignisse und wird in der Oberfläche kenntlich gemacht.",
    ],
    "tests": [
        "python3 tests/regression/check_grow_intelligence_noise_filter.py",
        "python3 tests/regression/check_grow_intelligence_insights.py",
        "python3 tests/regression/check_grow_intelligence_events.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
