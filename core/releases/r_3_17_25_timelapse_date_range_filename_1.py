"""Growstar 3.17.25 / GROWCAM.TIMELAPSE-DATE-RANGE.1 release metadata."""

RELEASE = {
    "version": "3.17.25",
    "date": "2026-09-23",
    "phase": "GROWCAM.TIMELAPSE-DATE-RANGE.1",
    "title": "Zeitraffer-Zeitraum und beschriftete Videodateien",
    "summary": "Zeitraffer-Videos können nach Start- und Enddatum begrenzt werden und tragen Station und Erstellungsdatum im Dateinamen.",
    "changes": [
        "Leeres Start- und Enddatum schließt alle archivierten Bilder des Durchgangs ein.",
        "Datumsauswahl, Vorschau-Bildanzahl und FFmpeg-Auftrag berücksichtigen beide Grenzen einschließlich der Randtage.",
        "Unzulässige oder leere Zeiträume werden vor dem Start abgefangen.",
        "Neue Videos enthalten Station und Erstellungsdatum im Dateinamen; ältere erhalten einen beschreibenden Downloadnamen.",
        "MP4 wird weiterhin als Anhang mit video/mp4 ausgeliefert.",
    ],
    "tests": [
        "python3 tests/regression/check_growcam_render_start_date.py",
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_growcam_timelapse_progress.py",
        "python3 tests/regression/check_release_loader.py",
    ],
}
