"""Growstar release node 3.11.9 / SF.3C."""

RELEASE = {
    "version": "3.11.9",
    "date": "2026-08-23",
    "phase": "SF.3C",
    "title": "Spider-Farmer-GGS als native read-only Systemoberfläche",
    "summary": (
        "Der bereits real verifizierte Spider-Farmer-Controller-/Geräte-State "
        "wird erstmals direkt in Growstars Systemoberfläche dargestellt. "
        "Controller, Onlinezustand, Umweltsensor, Licht, Ventilator, Gebläse "
        "und erkannte Outlet-Kanäle werden aus dem bestehenden normalisierten "
        "SF.3A/SF.3B-Modell gelesen. SF.3C fügt bewusst noch keinen Schreibpfad "
        "zum GGS hinzu."
    ),
    "changes": (
        "Unter /system/spiderfarmer existiert eine native mobilfreundliche Growstar-Seite für beobachtete GGS-Controller.",
        "Die Systemseite erhält eine eigene Spider-Farmer-Karte als sichtbaren Einstieg.",
        "Ein einzelner GET-Endpunkt /api/spiderfarmer/controllers liefert ausschließlich das bestehende normalisierte Controller-/Gerätemodell.",
        "Die Oberfläche zeigt Onlinezustand, Controller-ID, PID, Prefix und den unveränderten Bridge-last_seen-Zeitstempel.",
        "Environment-, Licht-, Ventilator-, Gebläse- und Outlet-Werte werden aus den bereits vorhandenen effective-Werten dargestellt.",
        "Ventilator-Run-Level, Standby-Level, Oszillation, Natural Wind, Zyklus und Zeitplan werden angezeigt, sobald sie im persistierten Config-State beobachtet wurden.",
        "Die Browseransicht aktualisiert den read-only Zustand alle fünf Sekunden und besitzt zusätzlich einen manuellen Aktualisieren-Button.",
        "Es wird kein neues Spider-Farmer-State-Modell eingeführt; SF.3C verwendet direkt services.spiderfarmer.list_controllers().",
        "Es existiert weiterhin kein POST-, PUT-, PATCH-, DELETE-, MQTT-Publish-, Socket- oder setConfigField-Sendepfad für Spider Farmer.",
    ),
    "tests": (
        "check_spiderfarmer_ui.py prüft Page- und GET-API-Registrierung.",
        "Die Regression verlangt, dass der API-Pfad ausdrücklich read_only=True und Phase SF.3C meldet.",
        "Die UI muss die bereits normalisierten effective-Gerätewerte verwenden und darf keine Roh-MQTT-Payload darstellen.",
        "Statische Guards blockieren Spider-Farmer-Schreibmethoden und bekannte Transport-/Command-Sendepfade in der neuen UI-Integration.",
        "Der neue Einzeldatei-Release-Node bestätigt gleichzeitig den CORE.R3-Release-Workflow ohne Änderung an loader.py oder current.py.",
    ),
}
