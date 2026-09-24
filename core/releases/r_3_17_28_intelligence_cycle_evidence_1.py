"""Growstar 3.17.28 / INTELLIGENCE.CYCLE-EVIDENCE.1 release metadata."""

RELEASE = {
    "version": "3.17.28",
    "date": "2026-09-24",
    "phase": "INTELLIGENCE.CYCLE-EVIDENCE.1",
    "title": "Prüfbare Gerätezyklen in Grow Intelligence",
    "summary": "Gerätezyklen zeigen jetzt EIN/AUS-Paare mit Ereignisnummern und Dauer; Kurztakt-Hinweise verwenden vergleichbare Phasen.",
    "changes": [
        "Jede Gerätekarte zeigt die letzten drei vollständigen EIN/AUS-Paare mit exakter Dauer.",
        "Die neue paginierte Detailansicht zeigt alle auswertbaren Zyklen eines Geräts und Zeitraums mit Belegen.",
        "Drei Minuten und eine Sekunde wird nicht als Kurzzyklus gewertet.",
        "Kurztakt-Hinweise beruhen nur auf Paaren derselben App-Sitzung mit durchgehendem ENV-Modus.",
        "Ältere Ereignisse ohne Sitzung und Wechsel der Regelart bleiben als eingeschränkt vergleichbar sichtbar.",
        "Vorhandene Temperatur- und Feuchtewerte zeigen Differenzen zwischen zwei Schaltzeitpunkten ohne Kausalitätsbehauptung.",
        "Historische Ereignisse und Regelung bleiben unverändert; keine Datenbankmigration.",
    ],
    "tests": [
        "python3 tests/regression/check_grow_intelligence_cycle_evidence.py",
        "python3 tests/regression/check_grow_intelligence_device_activity.py",
        "python3 tests/regression/check_grow_intelligence_cycle_context.py",
        "python3 tests/regression/check_grow_intelligence_insights.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
