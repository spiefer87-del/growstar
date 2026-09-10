"""Growstar 3.16.37 / PLANT.CAMERA.4 release metadata."""

RELEASE = {
    "version": "3.16.37",
    "date": "2026-09-10",
    "phase": "PLANT.CAMERA.4",
    "title": "Kamera-Seite nach Archivausbau wieder erreichbar",
    "summary": (
        "Die Zeitraffer-Galerie greift eindeutig auf ihre Bilderliste zu, "
        "sodass die erweiterte Kamera-Seite ohne Jinja-Namenskonflikt lädt."
    ),
    "changes": (
        "Der Galerie-Iterator verwendet die explizite Dict-Schlüsselnotation und kollidiert nicht mehr mit der Python-Methode items().",
        "Der Kamera-Regressionstest verbietet den mehrdeutigen Jinja-Zugriff dauerhaft.",
        "Livestream, Vollbild-Zoom, Bildverwaltung und Videoeinstellungen aus 3.16.36 bleiben unverändert erhalten.",
    ),
    "tests": (
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
