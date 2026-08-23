"""Growstar release node 3.11.16 / SF.4D."""

RELEASE = {
    "version": "3.11.16",
    "date": "2026-08-23",
    "phase": "SF.4D",
    "title": "Erster kontrollierter Spider-Farmer-Schreibpfad",
    "summary": (
        "Die in SF.4C gespeicherten Controller-Sollwerte können jetzt über die "
        "bereits bestehende lokale GGS-Bridge an den zugeordneten Spider-Farmer-"
        "Controller gesendet werden. Growstar erzeugt dabei keine freie oder "
        "geratene GGS-Konfiguration, sondern verwendet ausschließlich ein zuvor "
        "real beobachtetes DOWN/setConfigField-Paket als vollständiges Template "
        "und ändert darin nur die explizit unterstützten Sollwertfelder."
    ),
    "changes": (
        "Die historische SF.1 ReadOnly-Proxy- und Decoderdatei bleiben unverändert erhalten.",
        "SF.4D führt einen getrennten opt-in CommandSpiderFarmerProxy ein.",
        "Der Command-Proxy nutzt ausschließlich die bereits aktive lokale Controller-TLS/MQTT-Sitzung und öffnet keinen zweiten MQTT-Client.",
        "Growstar und Bridge kommunizieren über einen privaten UNIX-Socket im geschützten Spider-Farmer-State-Verzeichnis.",
        "Command-Payloads werden aus dem neuesten real beobachteten DOWN/setConfigField-Rohpaket des konkreten Controllers und Moduls erzeugt.",
        "Firmware-spezifische Felder, Zeitpläne, Natural-Wind- und sonstige unbekannte Werte bleiben im beobachteten Template unverändert erhalten.",
        "Ventilatorstufe wird auf das beobachtete Fan-Feld maxSpeed geschrieben.",
        "Oszillation wird auf das beobachtete Fan-Feld shakeLevel geschrieben.",
        "Blower-Level wird auf maxSpeed geschrieben; Licht-Level auf mLevel.",
        "Controller-Zuordnung, PID, Modul und Sollwerte werden weiterhin aus Growstars provider-neutralem Geräte-/Controller-Modell abgeleitet.",
        "Geräte-Konfiguration wird auch bei Bridge-Fehlern lokal gespeichert; die API liefert controller_apply mit dem tatsächlichen Sendestatus zurück.",
        "Die Geräte-UI zeigt getrennt an, ob lokal gespeichert und ob an Spider Farmer gesendet wurde.",
        "SF.4D sendet MQTT QoS 0, damit keine künstlichen QoS-1-Packet-ID/PUBACK-Zustände in die Cloud-Sitzung eingeführt werden.",
        "Der systemd-Dienst aktiviert den Command-Pfad explizit mit GROWSTAR_SF_COMMANDS=1.",
    ),
    "tests": (
        "check_spiderfarmer_command_path.py beweist, dass nur maxSpeed und shakeLevel geändert werden und alle übrigen beobachteten Fan-Felder erhalten bleiben.",
        "Das beobachtete keyPath und DOWN-Topic werden unverändert wiederverwendet.",
        "Der erzeugte MQTT-PUBLISH wird vom bestehenden Decoder wieder korrekt gelesen.",
        "Die historische SF.1 ReadOnly-Proxydatei bleibt ohne Command-Vokabular und der alte MQTT-Decoder bleibt encoderfrei.",
        "Der neue Command-Dienst ist ausschließlich über einen lokalen UNIX-Socket erreichbar.",
    ),
}
