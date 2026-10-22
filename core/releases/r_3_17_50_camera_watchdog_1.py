"""Growstar 3.17.50 / CAMERA.WATCHDOG.1."""

RELEASE = {
    "version": "3.17.50",
    "date": "2026-10-22",
    "phase": "CAMERA.WATCHDOG.1",
    "title": "Kamera-Aufnahmen und Zeitraffer überwachen",
    "summary": "Watchdog und Telegram melden Kameraausfälle je Station und entwarnen nach neuen Aufnahmen.",
    "changes": [
        "Der Watchdog zeigt Kamera-Zustand, letzte Aufnahme, Archivzustand und letzten Aufnahmefehler pro Station.",
        "Nach zwei fehlgeschlagenen Versuchen oder einer Aufnahme-Lücke über mindestens fünf Minuten wird je Kamera alarmiert.",
        "Ein aktiver Zeitraffer ohne neue Archivbilder erhält eine eigene Meldung; deaktivierte und beendete Pläne bleiben ruhig.",
        "Die Telegram-Regel Kameras kann getrennt ein- oder ausgeschaltet werden; Entwarnungen folgen dem ersten neuen Bild.",
    ],
    "tests": [
        "python3 tests/regression/check_camera_health_alerts.py",
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_growcam_multi_camera.py",
        "python3 tests/regression/check_notifications.py",
        "python3 tests/regression/check_release_loader.py",
    ],
}
