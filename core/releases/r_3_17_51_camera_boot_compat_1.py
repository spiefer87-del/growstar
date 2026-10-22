"""Growstar 3.17.51 / CAMERA.BOOT.COMPAT.1."""

RELEASE = {
    "version": "3.17.51",
    "date": "2026-10-22",
    "phase": "CAMERA.BOOT.COMPAT.1",
    "title": "Kamera-Route nach Watchdog-Patch wieder startfähig",
    "summary": "Die von älteren Medienrouten erwarteten Kamera-Funktionen bleiben verfügbar.",
    "changes": [
        "Kompatible Funktionen für nächste Zeitrafferaufnahme, Tageszählung und Video-Downloadname ergänzt.",
        "Der Gunicorn-Worker kann die weiterhin installierte Medienroute wieder importieren.",
    ],
    "tests": [
        "python3 tests/regression/check_growcam_route_compatibility.py",
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_camera_health_alerts.py",
        "python3 tests/regression/check_release_loader.py",
    ],
}
