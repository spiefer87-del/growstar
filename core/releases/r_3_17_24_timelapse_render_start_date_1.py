"""Growstar 3.17.24 / GROWCAM.RENDER-START-DATE.1 release metadata."""

RELEASE = {
    "version": "3.17.24",
    "date": "2026-09-23",
    "phase": "GROWCAM.RENDER-START-DATE.1",
    "title": "Zeitraffer-Erstellung mit Startdatum und getrennten Bereichen",
    "summary": "Videoerstellung, Videos und Bilder erhalten getrennte Bereiche; das gewählte Startdatum begrenzt die tatsächlich verwendeten Aufnahmen.",
    "changes": [
        "Videorendering verwendet auf Wunsch nur Bilder ab dem gewählten lokalen Datum.",
        "Video-Erstellung und Bildarchiv sind kompakte, unabhängig aufklappbare Bereiche.",
        "Aktuelles Video und letzte Videos zeigen ihr Erstellungsdatum.",
        "Bildanzahl und Fortschritt beziehen sich auf die tatsächliche Auswahl.",
    ],
    "tests": [
        "python3 tests/regression/check_growcam_render_start_date.py",
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_growcam_timelapse_progress.py",
        "python3 tests/regression/check_release_loader.py",
    ],
}
