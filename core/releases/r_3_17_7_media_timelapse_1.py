"""Growstar 3.17.7 / MEDIA.TIMELAPSE.1 release metadata."""

RELEASE = {
    "version": "3.17.7",
    "date": "2026-09-12",
    "phase": "MEDIA.TIMELAPSE.1",
    "title": "Neustartfeste Zeitrafferpläne",
    "summary": (
        "Zeitrafferaufnahmen folgen festen Uhrzeit-Slots mit Start und Ende, "
        "ohne nach einem App- oder Raspberry-Neustart zu wandern."
    ),
    "changes": [
        "Jede Kamera speichert den ersten und letzten Aufnahmezeitpunkt ihres Zeitrafferplans.",
        "Der Scheduler berechnet fällige Aufnahmen aus persistenten Wandzeiten statt aus Prozesslaufzeit.",
        "Verpasste Intervalle werden nicht in einer Aufnahmeserie nachproduziert.",
        "Die Zeitrafferseite zeigt Status, letzte Aufnahme, nächsten Slot und geplante Bildanzahl.",
        "Ein nicht auf dem Intervall liegender Endzeitpunkt erhält eine eigene Abschlussaufnahme.",
    ],
    "tests": [
        "python3 tests/regression/check_timelapse_schedule.py",
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_growcam_recording_and_photo.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
