"""Growstar release node 3.11.12 / SF.4A."""

RELEASE = {
    "version": "3.11.12",
    "date": "2026-08-23",
    "phase": "SF.4A",
    "title": "Provider-neutrales Capability-Routing für Aktor und Controller",
    "summary": (
        "Growstar trennt erstmals die Stromversorgung eines logischen Geräts "
        "von zusätzlichen Controller-Funktionen. Der bestehende Shelly bleibt "
        "in SF.4A der Power-Aktor, während level und oscillation unabhängig "
        "einem kompatiblen Controller-Target zugeordnet werden können. Die "
        "Architektur ist provider-neutral und berücksichtigt bereits zukünftige "
        "Spider-Farmer-Steckdosen als Power-Aktoren, ohne sie vorzeitig "
        "freizuschalten."
    ),
    "changes": (
        "core/capability_routing.py führt ein generisches Capability-Routing für power, level und oscillation ein.",
        "Die bestehenden IP/Relay-Shelly-Zuordnungen bleiben unverändert die alleinige aktive power-Quelle und werden nur als Legacy-Power-Route gespiegelt.",
        "Spider-Farmer-Licht, Fan und Blower werden aus dem bereits normalisierten Geräteinventar als generische Modulationsziele projiziert.",
        "Ein Spider-Farmer-Controller ist nicht an einen gleichnamigen Growstar-Aktor gebunden; jedes Target kann jedem logisch kompatiblen Gerät zugeordnet werden.",
        "Level und Oszillation sind getrennte Routen und können später unabhängig durch die zentrale Growstar-Regelung gesetzt werden.",
        "Target/Capability-Konflikte verhindern, dass dieselbe physische Funktion gleichzeitig mehreren logischen Geräten gehört.",
        "Spider-Farmer-Outlet-Kanäle erscheinen bereits als zukünftige power-Targets, bleiben in SF.4A jedoch assignment_enabled=False und writable=False.",
        "Die stationsbezogene Konfiguration wird unter CAPABILITY_ROUTES persistiert, ohne bestehende IP_/RELAY_-Felder zu verändern.",
        "GET /api/control-targets liefert das provider-neutrale Target-Inventar.",
        "GET/POST /api/tents/<tent_id>/capability-routing liest beziehungsweise speichert ausschließlich lokale Routing-Metadaten.",
        "SF.4A erzeugt und sendet ausdrücklich noch keinen Shelly- oder Spider-Farmer-Hardwarebefehl.",
    ),
    "tests": (
        "check_capability_routing.py prüft Licht-Level, Fan-Level/Oszillation, Blower-Level und gesperrte zukünftige Outlet-Power-Targets.",
        "Die Regression weist einen Spider-Farmer-Fan bewusst einem anderen kompatiblen Growstar-Aktor zu und bestätigt damit die freie Zuordnung.",
        "Semantisch falsche Capability-Zuordnungen und Target/Capability-Doppelbelegungen werden blockiert.",
        "Der vorhandene Shelly-Powerpfad bleibt neben einer unabhängigen Spider-Farmer-Levelroute sichtbar und unverändert.",
        "Statische Guards verbieten Netzwerk-, MQTT-, Socket-, HTTP- und setConfigField-Sendepfade im neuen Routing-Layer.",
        "CORE.R3 wird eingehalten: nur r_3_11_12_sf_4a.py wird als neuer Release-Node ergänzt.",
    ),
}
