"""Growstar release node 3.11.11 / SF.3C.1."""

RELEASE = {
    "version": "3.11.11",
    "date": "2026-08-23",
    "phase": "SF.3C.1",
    "title": "Spider Farmer direkt im Grow-Control-Dashboard sichtbar",
    "summary": (
        "Die in SF.3C eingeführte native Spider-Farmer-Seite erhält einen "
        "direkten sichtbaren Einstieg im Grow-Control-Dashboard unter "
        "System & Infrastruktur. Das Hauptdashboard bleibt unverändert."
    ),
    "changes": (
        "Das Grow-Control-Dashboard erhält unter System & Infrastruktur eine eigene Spider-Farmer-Kachel.",
        "Die Kachel führt auf die bereits vorhandene Route /system/spiderfarmer.",
        "Der Einstieg liegt im bestehenden hardware.view-Berechtigungsblock gemeinsam mit Hardware und Verbindungen.",
        "Die Kachel kennzeichnet den aktuellen Integrationsstand sichtbar als SF READ-ONLY.",
        "Das Growstar-Hauptdashboard wird ausdrücklich nicht verändert.",
        "Spider-Farmer-State, Controller-API und read-only Geräte-Modell bleiben unverändert.",
        "Es entsteht kein POST-, PUT-, PATCH-, DELETE-, MQTT-Publish- oder setConfigField-Schreibpfad.",
    ),
    "tests": (
        "check_spiderfarmer_visibility.py prüft den sichtbaren Einstieg im Grow-Control-Dashboard.",
        "Der Test stellt sicher, dass das Hauptdashboard keine Spider-Farmer-Kachel erhält.",
        "Die bestehende Spider-Farmer-Systemseite und GET-Controller-API müssen weiterhin registriert sein.",
        "Bekannte Spider-Farmer-Schreibrouten bleiben in SF.3C.1 ausgeschlossen.",
    ),
}
