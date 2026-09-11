"""Growstar 3.16.41 / HARDWARE.SHELL.1 release metadata."""

RELEASE = {
    "version": "3.16.41",
    "date": "2026-09-11",
    "phase": "HARDWARE.SHELL.1",
    "title": "Hardware & Setup als eigenständiges Modul",
    "summary": (
        "Technische Geräte, Sensorquellen, Verbindungen und Raspberry-Setup "
        "werden aus Grow Control in einen strukturierten Hardware-Manager verschoben."
    ),
    "changes": [
        "Das Hauptmenü und Startdashboard besitzen das eigenständige Modul Hardware & Setup.",
        "Geräte, Sensoren, Verbindungen, Spider Farmer, Watchdog, Setup, Netzwerk, Alarme und Systemstatus sind dort strukturiert gebündelt.",
        "Grow Control enthält keine Hardware- und Setup-Verwaltung mehr.",
        "GrowCam-IP, RTSP-Port, Benutzer und RTSP-Pfad werden im Geräte-Manager mit hardware.configure verwaltet.",
        "Medien speichert weiterhin Aufnahmeplan, Zuordnung, Livequalität und Zeitraffer, ohne technische Verbindungswerte zu überschreiben.",
    ],
    "tests": [
        "python3 tests/regression/check_hardware_module_navigation.py",
        "python3 tests/regression/check_app_shell_navigation.py",
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
