"""Growstar 3.17.5 / HARDWARE.ACCORDION.1 release metadata."""

RELEASE = {
    "version": "3.17.5",
    "date": "2026-09-12",
    "phase": "HARDWARE.ACCORDION.1",
    "title": "Hardware-Manager mit übersichtlichen Klappbereichen",
    "summary": (
        "Gerätesuche, Sensorinventar und Aktoren werden in drei exklusive "
        "Klappbereiche gegliedert; die Statusübersicht bleibt dauerhaft sichtbar."
    ),
    "changes": [
        "Neue Geräte bündelt LAN-Gateway-, Shelly- und VIVOSUN-Suche.",
        "Sensoren bündelt Bluetooth-, MQTT- und Spider-Farmer-Quellen.",
        "Aktoren erhalten einen eigenen kompakten Klappbereich.",
        "Beim Öffnen eines Bereichs schließt Growstar den zuvor geöffneten automatisch.",
        "Sensor- und Aktoranzahl werden direkt in den Modulköpfen angezeigt.",
        "Die Hardware-Statusbox bleibt unabhängig vom Akkordeon permanent sichtbar.",
    ],
    "tests": [
        "python3 tests/regression/check_hardware_accordion.py",
        "python3 tests/regression/check_hardware_provisioning_discovery.py",
        "python3 tests/regression/check_hardware_module_navigation.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
