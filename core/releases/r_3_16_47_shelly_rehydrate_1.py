"""Growstar 3.16.47 / SHELLY.REHYDRATE.1 release metadata."""

RELEASE = {
    "version": "3.16.47",
    "date": "2026-09-11",
    "phase": "SHELLY.REHYDRATE.1",
    "title": "Persistierte Shellys wieder aktiv abfragen",
    "summary": (
        "Growstar stellt gespeicherte Shelly-Gateways nach einem Neustart mit ihrem "
        "vollständigen RPC-Client wieder her und aktualisiert sie unabhängig von mDNS."
    ),
    "changes": [
        "Shelly-Inventareinträge werden als ShellyGateway statt als abstraktes Gateway geladen.",
        "Der Hardware-Refresh repariert verbliebene alte Laufzeitobjekte automatisch.",
        "Power Strips und ihre zugeordneten Relais erhalten wieder Livezustand, Uptime und Sichtzeit.",
        "Ein echter erfolgreicher RPC-Read bleibt Voraussetzung für den Status Online.",
    ],
    "tests": [
        "python3 tests/regression/check_shelly_inventory_rehydration.py",
        "python3 tests/regression/check_hardware_transport_cleanup.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
