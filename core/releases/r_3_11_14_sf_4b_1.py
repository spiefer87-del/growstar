"""Growstar release node 3.11.14 / SF.4B.1."""

RELEASE = {
    "version": "3.11.14",
    "date": "2026-08-23",
    "phase": "SF.4B.1",
    "title": "Controller werden als unteilbare physische Geräte zugeordnet",
    "summary": (
        "Die Controller-Zuordnung wird an die reale Spider-Farmer-Hardware "
        "angepasst. Ein physisches Controller-Gerät gehört immer vollständig "
        "zu genau einem logischen Growstar-Gerät. Funktionen wie Level und "
        "Oszillation eines Ventilators können nicht mehr separat auf "
        "verschiedene Growstar-Aktoren verteilt werden. Power bleibt weiterhin "
        "ein unabhängiger Aktorpfad über Shelly."
    ),
    "changes": (
        "CONTROLLER_ASSIGNMENTS ersetzt die getrennte per-Capability-Zuordnung als neue Quelle für Controller-Mappings.",
        "Ein physisches Controller-Target wird als Einheit einem logischen Growstar-Gerät zugewiesen.",
        "Ventilator-Controller bringen Level und Oszillation gemeinsam mit; beide Fähigkeiten sind nicht separat belegbar.",
        "Light-, Fan- und Blower-Controller besitzen explizite Gerätefamilien, sodass nur semantisch passende Ziele angeboten werden.",
        "Ventilator und Ventilator 2 akzeptieren nur vollständige Fan-Controller mit Level und Oszillation.",
        "Abluft/Lüfter akzeptiert nur Blower-Controller; Beleuchtung und Licht 2 nur Light-Controller.",
        "Ein physisches Controller-Gerät kann global nur einem Growstar-Gerät gehören.",
        "Bestehende SF.4B-CAPABILITY_ROUTES werden automatisch gelesen, sofern alle Fähigkeiten eines Geräts bereits auf dasselbe Target zeigen.",
        "Beim nächsten Speichern eines Geräts wird dessen Legacy-CAPABILITY_ROUTES-Eintrag entfernt und die neue Geräte-Zuordnung persistiert.",
        "Die Verbindungen-Seite zeigt pro Growstar-Gerät nur noch ein Controller-Dropdown und den automatisch enthaltenen Funktionsumfang.",
        "Spider-Farmer-Steckdosen bleiben als zukünftige Power-Aktoren modelliert, aber weiterhin gesperrt.",
        "SF.4B.1 sendet weiterhin keinerlei Spider-Farmer- oder Shelly-Command.",
    ),
    "tests": (
        "check_capability_routing.py blockiert explizit Split-Zuordnungen von Level und Oszillation.",
        "Controller-Familie und vollständiger benötigter Funktionssatz müssen zum logischen Growstar-Gerät passen.",
        "Ein physisches Controller-Gerät darf nicht zwei Growstar-Geräten gleichzeitig zugeordnet werden.",
        "Bestehende saubere SF.4B-Zuordnungen werden migrationskompatibel als ein Controller-Gerät erkannt.",
        "check_capability_routing_ui.py verlangt genau ein Controller-Dropdown pro Gerät und verbietet alte js-capability-Einzelfelder.",
        "Statische Guards bestätigen, dass weiterhin kein Hardware-/Command-Transport eingeführt wird.",
    ),
}
