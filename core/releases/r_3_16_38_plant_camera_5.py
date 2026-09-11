"""Growstar 3.16.38 / PLANT.CAMERA.5 release metadata."""

RELEASE = {
    "version": "3.16.38",
    "date": "2026-09-10",
    "phase": "PLANT.CAMERA.5",
    "title": "Stationsbezogener Livekamera-Schnellzugriff",
    "summary": (
        "Eine aktivierte GrowCam erscheint automatisch an der zugewiesenen Station "
        "neben dem Tag-/Nacht-Symbol und öffnet direkt eine bildschirmfüllende Liveansicht."
    ),
    "changes": [
        "Der LIVE-Kameraknopf wird ausschließlich an der in der GrowCam-Konfiguration ausgewählten Station angezeigt.",
        "Der neue schlanke Liveviewer füllt den verfügbaren Bildschirm und besitzt Zoom, Verschieben, Einpassen und Browser-Vollbild.",
        "Der Rückweg führt direkt zur zugeordneten Grow-Control-Station; Kamera-Konfiguration und Archive bleiben getrennt.",
    ],
    "tests": [
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
        "python3 -m compileall -q routes/dashboard.py routes/camera.py core/releases/r_3_16_38_plant_camera_5.py",
    ],
}
