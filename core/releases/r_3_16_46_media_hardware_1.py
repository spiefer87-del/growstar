"""Growstar 3.16.46 / MEDIA.HARDWARE.1 release metadata."""

RELEASE = {
    "version": "3.16.46",
    "date": "2026-09-11",
    "phase": "MEDIA.HARDWARE.1",
    "title": "GrowCam-Durchgangsfotos und eindeutige Gerätesichtbarkeit",
    "summary": (
        "Durchgangsfotos können direkt von einer GrowCam stammen, das Hauptmenü folgt "
        "der fachlichen Reihenfolge und der Gerätemanager zeigt VIVOSUN sowie Sichtzeiten eindeutig."
    ),
    "changes": [
        "Das Durchgangsfoto-Formular kann einen frischen Schnappschuss jeder aktiven GrowCam übernehmen.",
        "Pflanzenmanagement und Medien stehen vor Hardware & Setup; Administrator ist klappbar.",
        "Ein per Pico gelesener VIVOSUN bleibt genau einmal als physisches Bluetooth-Gerät sichtbar.",
        "Gateway-, Bluetooth- und MQTT-Karten zeigen den Zeitpunkt der letzten Sichtung.",
    ],
    "tests": [
        "python3 tests/regression/check_media_navigation_device_visibility.py",
        "python3 tests/regression/check_hardware_transport_cleanup.py",
        "python3 tests/regression/check_app_shell_navigation.py",
        "python3 tests/regression/check_plant_photo_management.py",
        "python3 tests/regression/check_vivosun_source_handover.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
