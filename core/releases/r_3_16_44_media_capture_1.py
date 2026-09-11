"""Growstar 3.16.44 / MEDIA.CAPTURE.1 release metadata."""

RELEASE = {
    "version": "3.16.44",
    "date": "2026-09-11",
    "phase": "MEDIA.CAPTURE.1",
    "title": "Zeitraffer-Modul, Videoaufnahme und GrowCam-Pflanzenfoto",
    "summary": (
        "Kamera und Zeitraffer werden getrennte Medienmodule; Growstar zeichnet "
        "direkte RTSP-Videos auf und übernimmt GrowCam-Schnappschüsse als Pflanzenfoto."
    ),
    "changes": [
        "Zeitraffer erhält neben Kamera einen eigenen Menüpunkt mit Kamera-, Durchgangs- und Intervallauswahl.",
        "Direkte Videoaufnahmen von 30 Sekunden bis 10 Minuten werden ohne erneute Kompression je Kamera und Durchgang gespeichert.",
        "Videoaufnahmen lassen sich im Medien-Explorer ansehen, herunterladen und kontrolliert löschen.",
        "Beim Anlegen eines Pflanzenfotos kann statt Handy oder Datei eine aktive GrowCam ausgewählt werden.",
        "Growstar nimmt dafür ein frisches Kamerabild auf, optimiert es wie jedes Pflanzenfoto und dokumentiert es im Journal.",
    ],
    "tests": [
        "python3 tests/regression/check_growcam_recording_and_photo.py",
        "python3 tests/regression/check_growcam_multi_camera.py",
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_plant_photo_management.py",
        "python3 tests/regression/check_app_shell_navigation.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
