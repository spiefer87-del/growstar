"""Growstar 3.17.26 / TIMELAPSE.VIDEO-BUTTONS.1 release metadata."""

RELEASE = {
    "version": "3.17.26",
    "date": "2026-09-23",
    "phase": "TIMELAPSE.VIDEO-BUTTONS.1",
    "title": "Videoliste mit kompakten Schaltflächen",
    "summary": "Die letzten Zeitraffer-Videos werden als gut bedienbare Schaltflächen mit Erstellungsdatum angezeigt.",
    "changes": [
        "Videolinks nutzen die Growstar-Farben ohne Browser-Standardlink und Unterstreichung.",
        "Die gesamte Videozeile ist auf Mobilgeräten anklickbar und zeigt ihr Erstellungsdatum.",
        "Fokus und Hover sind deutlich sichtbar; die CSS-Version verhindert alte zwischengespeicherte Stile.",
    ],
    "tests": [
        "python3 tests/regression/check_growcam_render_start_date.py",
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
