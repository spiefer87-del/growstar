"""Growstar release node 3.11.13 / SF.4B."""

RELEASE = {
    "version": "3.11.13",
    "date": "2026-08-23",
    "phase": "SF.4B",
    "title": "Controller-Zuordnung sauber in bestehende Verbindungen-Seite integriert",
    "summary": (
        "Das in SF.4A eingeführte provider-neutrale Capability-Routing wird "
        "ohne neue Paralleloberfläche in Growstars bestehende Verbindungen-Seite "
        "integriert. Stromversorgung über Shelly und zusätzliche Controller-"
        "Funktionen wie Level/Dimmen und Oszillation sind dort klar getrennt, "
        "aber stations- und gerätebezogen gemeinsam erreichbar."
    ),
    "changes": (
        "templates/connections.html bleibt die zentrale Oberfläche für Hardware-Zuordnungen.",
        "Der bestehende Shelly-/Power-Bereich und seine Safety-/Konfliktlogik bleiben unverändert erhalten.",
        "Unterhalb der Stromzuordnungen erscheint ein eigener Controller-Funktionen-Bereich für Level/Dimmen und Oszillation.",
        "Controller-Targets werden direkt aus der bestehenden SF.4A Capability-Routing-API geladen und capability-basiert gefiltert.",
        "Ein Spider-Farmer-Fan, Licht- oder Blower-Target bleibt frei einem kompatiblen logischen Growstar-Gerät zuweisbar.",
        "Controller-Zuordnungen sind in der UI nur im bestehenden Geräte-Modus OFF editierbar.",
        "Power- und Controller-Zuordnungen besitzen bewusst getrennte Speichern-Aktionen, damit kein pseudo-atomarer Misch-POST mit Teilpersistenz entsteht.",
        "Globale Target/Capability-Konflikte werden direkt auf der betroffenen Controller-Karte hervorgehoben.",
        "Spider-Farmer-Outlets bleiben durch assignment_enabled=False weiterhin unsichtbar als auswählbare Power-Quelle.",
        "SF.4B führt weiterhin keinen Spider-Farmer-Command-, MQTT-, Socket- oder setConfigField-Sendepfad ein.",
    ),
    "tests": (
        "check_capability_routing_ui.py schützt die bestehende Shelly-Zuordnung und den neuen Controller-Bereich gemeinsam.",
        "Die Regression verlangt capability-gefilterte und assignment_enabled-gefilterte Target-Auswahl.",
        "Die bestehende OFF-Sicherheitslogik muss auch Controller-Zuordnungen sperren.",
        "Power- und Controller-Persistenz müssen getrennte Speichern-Aktionen behalten.",
        "Statische Guards verbieten bekannte Spider-Farmer-Command-/Transportpfade in der UI.",
    ),
}
