"""Growstar 3.16.35 / PLANT.CAMERA.2 release metadata."""

RELEASE = {
    "version": "3.16.35",
    "date": "2026-09-10",
    "phase": "PLANT.CAMERA.2",
    "title": "GrowCam-Livestream und Durchgangs-Zeitraffer",
    "summary": (
        "Die VIVOSUN GrowCam C4 liefert jetzt einen browserfähigen lokalen "
        "Livestream und archiviert Aufnahmen je Pflanzendurchgang für MP4-Zeitraffer."
    ),
    "changes": (
        "Growstar transkodiert den HEVC-RTSP-Stream bei geöffneter Live-Ansicht in einen browserfähigen MJPEG-Stream.",
        "Live-Auflösung und Bildrate sind konfigurierbar; der empfohlene Pi-5-Standard beträgt 960 Pixel bei fünf Bildern pro Sekunde.",
        "Eine GrowCam kann einem vorhandenen Pflanzendurchgang zugeordnet werden und ist direkt aus dessen Detailseite erreichbar.",
        "Zeitrafferbilder werden mit frei wählbarem Intervall getrennt nach Durchgang archiviert.",
        "Eine konfigurierbare Aufbewahrungszeit und maximal fünf Videos je Durchgang begrenzen den Speicherverbrauch.",
        "Growstar rendert die archivierten Bilder im Hintergrund als H.264-MP4 mit auswählbarer Bildrate und zeigt das neueste Video direkt an.",
        "Livebild, Archiv, Video und Bedienung verwenden die bestehenden rollenbasierten Pflanzen-Rechte.",
    ),
    "tests": (
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
        "python3 -m compileall -q app.py services/growcam.py routes/camera.py core/releases/r_3_16_35_plant_camera_2.py",
    ),
}
