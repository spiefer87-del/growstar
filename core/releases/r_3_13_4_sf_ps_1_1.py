"""Growstar release node 3.13.4 / SF.PS1.1."""

RELEASE = {
    "version": "3.13.4",
    "date": "2026-08-26",
    "phase": "SF.PS1.1",
    "title": "Power-Strip-Erkennung und Outlet-Darstellung stabilisieren",
    "summary": (
        "Die Spider-Farmer-Systemseite verwendet jetzt eine zentrale robuste "
        "Power-Strip-Erkennung. Prefix PS bleibt die kanonische Identität; das "
        "bereits normalisierte Outlet-Inventar dient ausschließlich als sichere "
        "Read-UI-Fallback-Erkennung. O1..O10 werden vor dem Rendern eindeutig "
        "normalisiert und der Statusabruf umgeht Browser-Caches."
    ),
    "changes": (
        "Power-Strip-Zähler, Kartenname und Outlet-Steuerbarkeit verwenden denselben isPowerStrip()-Helper.",
        "Prefix PS bleibt der primäre Power-Strip-Indikator.",
        "Ein vorhandenes Outlet-Gerät mit beobachteten Kanälen dient als Read-UI-Fallback.",
        "Outlet-Kanäle werden auf O1..O10 normalisiert, sortiert und gegen doppelte UI-Einträge dedupliziert.",
        "GET /api/spiderfarmer/controllers wird in der UI mit cache=no-store geladen.",
        "SF.PS1.1 wird sichtbar in der Spider-Farmer-Seite angezeigt, damit alte Browser-Tabs sofort erkennbar sind.",
        "Serverseitige PS-Schreibsperre, MQTT-Bridge, Controller-Kommandos, Shelly, Regelung und Safety bleiben unverändert.",
    ),
    "tests": (
        "python3 tests/regression/check_spiderfarmer_powerstrip_ui_ps1_1.py",
        "python3 tests/regression/check_spiderfarmer_powerstrip_ps1.py",
        "python3 tests/regression/check_dashboard_controller_readback.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
