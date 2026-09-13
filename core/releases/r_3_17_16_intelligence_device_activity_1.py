"""Growstar 3.17.16 / INTELLIGENCE.DEVICE-ACTIVITY.1 release metadata."""

RELEASE = {
    "version": "3.17.16",
    "date": "2026-09-13",
    "phase": "INTELLIGENCE.DEVICE-ACTIVITY.1",
    "title": "Verdichtete Geräteaktivität",
    "summary": (
        "Grow Intelligence fasst bestätigte Relaiswechsel je Station und Aktor "
        "zu Zyklen, belegten Laufzeiten und vorsichtigen Taktungshinweisen zusammen."
    ),
    "changes": [
        "Geräteschaltungen werden je Station und Aktor zu kompakten Aktivitätskarten verdichtet.",
        "Jede Karte zeigt Schaltanzahl, vollständige Zyklen, belegte Laufzeit und mittlere Einschaltdauer.",
        "Eine noch aktive Phase wird separat ausgewiesen und nicht als vollständig belegte Laufzeit ausgegeben.",
        "Wiederholte kurze Einschaltphasen erzeugen erst ab einer belastbaren Mindestmenge einen vorsichtigen Taktungshinweis.",
        "Erkannte Kurztaktung erscheint zusätzlich als belegte Karte unter Aktuelle Erkenntnisse.",
        "Stations-, Zeitraum-, Kategorie- und Prioritätsfilter bleiben auch für die neue Übersicht eindeutig.",
        "Das vollständige Ereignisprotokoll bleibt unverändert erhalten und startet platzsparend eingeklappt.",
        "Alle Auswertungen bleiben read-only und verändern weder Regelung noch historische Ereignisse.",
    ],
    "tests": [
        "python3 tests/regression/check_grow_intelligence_device_activity.py",
        "python3 tests/regression/check_grow_intelligence_device_events.py",
        "python3 tests/regression/check_grow_intelligence_insights.py",
        "python3 tests/regression/check_grow_intelligence_events.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
