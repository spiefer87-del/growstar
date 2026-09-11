"""Growstar 3.16.45 / HARDWARE.TRANSPORT.1 release metadata."""

RELEASE = {
    "version": "3.16.45",
    "date": "2026-09-11",
    "phase": "HARDWARE.TRANSPORT.1",
    "title": "Eindeutige Sensortransporte und zentrale Kamera-Verbindungen",
    "summary": (
        "Growstar zeigt den VIVOSUN nur noch über seinen aktuell frischen Transport, "
        "bereinigt sichere Shelly-IP-Dubletten per MAC und verwaltet GrowCam-Netzwerkdaten "
        "auf der Seite Verbindungen."
    ),
    "changes": [
        "Ein frischer Pico/MQTT-Wert ersetzt den lokalen Raspberry-BLE-Eintrag im Recovery-Count.",
        "VIVOSUN-Hardwaredarstellung wird auf einen Pico-Controller und zwei echte Sensorquellen reduziert.",
        "Alte Shelly-IP-Inventareinträge werden ausschließlich bei identischer MAC entfernt.",
        "GrowCam-IP, RTSP-Port, Benutzer, Pfad und Station befinden sich unter Hardware & Setup → Verbindungen.",
    ],
    "tests": [
        "python3 tests/regression/check_hardware_transport_cleanup.py",
        "python3 tests/regression/check_vivosun_source_handover.py",
        "python3 tests/regression/check_vivosun_thb1s_integration.py",
        "python3 tests/regression/check_growcam_multi_camera.py",
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_hardware_module_navigation.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
