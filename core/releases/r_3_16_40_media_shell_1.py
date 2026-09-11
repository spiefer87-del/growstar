"""Growstar 3.16.40 / MEDIA.SHELL.1 release metadata."""

RELEASE = {
    "version": "3.16.40",
    "date": "2026-09-11",
    "phase": "MEDIA.SHELL.1",
    "title": "Medien als eigenständiges Growstar-Modul",
    "summary": (
        "Explorer, Foto-Manager und GrowCam werden aus dem Pflanzenmanagement "
        "gelöst und in einem eigenen Medienmodul zusammengeführt."
    ),
    "changes": [
        "Das Hauptmenü besitzt einen eigenständigen, aufklappbaren Bereich Medien mit Explorer, Foto-Manager und Kamera.",
        "Die Kameraeinstellungen und der Livestream sind ausschließlich über die neue Mediennavigation erreichbar.",
        "Pflanzenmanagement enthält keine doppelten Foto-, Kamera- oder Medienreiter mehr.",
        "Das Growstar-Startdashboard bietet Medien als eigenes Modul an.",
    ],
    "tests": [
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_plant_photo_management.py",
        "python3 tests/regression/check_photo_gallery_navigation.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
        "python3 -m compileall -q core/releases/r_3_16_40_media_shell_1.py",
    ],
}
