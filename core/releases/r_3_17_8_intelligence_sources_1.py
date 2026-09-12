"""Growstar 3.17.8 / INTELLIGENCE.SOURCES.1 release metadata."""

RELEASE = {
    "version": "3.17.8",
    "date": "2026-09-12",
    "phase": "INTELLIGENCE.SOURCES.1",
    "title": "Lebende Grow-Intelligence-Timeline",
    "summary": (
        "Relevante Zustandswechsel aus Watchdog, Profilen, Energie, Pflanzen "
        "und Medien fließen jetzt automatisch in die gemeinsame Timeline."
    ),
    "changes": [
        "Ein eigener, begrenzter Event-Writer entkoppelt die Timeline von Regelung und Watchdog.",
        "Alarme und Entwarnungen werden als zusammengehöriger Vorgang gespeichert.",
        "Tag-/Nachtwechsel sowie manuelle Grow-Profiländerungen werden protokolliert.",
        "Tages- und Gesamtresets der Energie erscheinen mit Auslöser und Umfang.",
        "Pflanzenphasen, Pflanzenstatus und neue Pflanzen- oder Durchgangsfotos werden erfasst.",
        "Zeitrafferpläne, fertige Zeitraffervideos und Kameraaufnahmen werden dokumentiert.",
        "Die Timeline zeigt Writer-Status und Ereigniszahlen je Quelle; Messwert- und Bildfluten bleiben außen vor.",
    ],
    "tests": [
        "python3 tests/regression/check_grow_intelligence_integration.py",
        "python3 tests/regression/check_grow_intelligence_events.py",
        "python3 tests/regression/check_energy_day_reset_schedule.py",
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_growcam_recording_and_photo.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
