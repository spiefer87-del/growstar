"""Growstar 3.17.23 / GROWCAM.TIMELAPSE-PROGRESS.1 release metadata."""

RELEASE = {
    "version": "3.17.23",
    "date": "2026-09-22",
    "phase": "GROWCAM.TIMELAPSE-PROGRESS.1",
    "title": "Echter Fortschrittsbalken für Zeitraffer-Videos",
    "summary": (
        "Die Zeitraffer-Seite zeigt während der Hintergrunderstellung den echten "
        "FFmpeg-Fortschritt mit Prozentwert, Arbeitsschritt und Bildzähler."
    ),
    "changes": [
        "FFmpeg schreibt während der Kodierung die Anzahl der verarbeiteten Bilder.",
        "Growstar berechnet daraus einen echten Fortschrittswert von 0 bis 100 Prozent.",
        "Die Zeitraffer-Seite aktualisiert den Ladebalken einmal pro Sekunde ohne Seitenwechsel.",
        "Arbeitsschritte unterscheiden Vorbereitung, Kodierung, Abschluss, Fertig und Fehler.",
        "Nach erfolgreichem Abschluss wird das neue Video automatisch eingeblendet.",
        "Fortschritt und Hintergrundauftrag bleiben für jede GrowCam getrennt.",
    ],
    "tests": [
        "python3 tests/regression/check_growcam_timelapse_progress.py",
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_growcam_multi_camera.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
