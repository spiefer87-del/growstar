"""Growstar 3.16.43 / CAMERA.MULTI.1 release metadata."""

RELEASE = {
    "version": "3.16.43",
    "date": "2026-09-11",
    "phase": "CAMERA.MULTI.1",
    "title": "Mehrkamera-Verwaltung für beliebig viele Stationen",
    "summary": (
        "Growstar verwaltet mehrere VIVOSUN GrowCam C4 unabhängig und übernimmt "
        "die bestehende Einzelkamera-Konfiguration automatisch."
    ),
    "changes": [
        "Der Hardware-Manager fügt eine neue Kamera allein über lokale IP-Adresse und Station hinzu.",
        "Jede Kamera besitzt eine stabile ID, eigene RTSP-Verbindung, eigenen Laufzeitstatus und getrennte Medienpfade.",
        "Die bisherige growcam.json wird beim nächsten Speichern verlustfrei in eine versionierte Kamera-Registry überführt.",
        "Kameraansicht, Liveviewer, Stations-Dashboard, Zeitraffer und Medien-Explorer transportieren die Kamera-ID durchgängig.",
        "Der Medien-Explorer kennzeichnet Zeitrafferbilder und Videos mit ihrer jeweiligen Kamera.",
    ],
    "tests": [
        "python3 tests/regression/check_growcam_multi_camera.py",
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_hardware_module_navigation.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
