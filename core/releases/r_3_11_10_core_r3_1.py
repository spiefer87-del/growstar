"""Growstar release node 3.11.10 / CORE.R3.1."""

RELEASE = {
    "version": "3.11.10",
    "date": "2026-08-23",
    "phase": "CORE.R3.1",
    "title": "Release-Regression dauerhaft versionsunabhängig gemacht",
    "summary": (
        "Der temporäre CORE.R1/CORE.R2-Migrationstest wird durch einen kleinen "
        "dauerhaften Architekturtest ersetzt. Der neue Test enthält keinerlei "
        "hart codierte aktuelle Growstar-Version, Phase oder Datum mehr und "
        "prüft ausschließlich Regeln, die für jeden zukünftigen Patch gelten."
    ),
    "changes": (
        "tests/regression/check_release_system.py ersetzt die migrationsspezifischen Prüfungen durch dauerhafte Release-Architektur-Invarianten.",
        "Die aktuelle Version, Phase und das Release-Datum werden ausschließlich aus dem automatisch höchsten entdeckten Release-Node abgeleitet.",
        "Jede r_*.py-Datei muss genau einen RELEASE-Node enthalten und ihr Dateiname muss dynamisch zu Version und Phase passen.",
        "Der Test schützt weiterhin gegen doppelte Versionen, unsortierte Releases, anwachsende current.py und Abweichungen zwischen Loader-Discovery und Dateisystem.",
        "Defensive Kopien von current_release() und release_history() bleiben ausdrücklich abgesichert.",
        "check_release_split.py bleibt nur als winziger Kompatibilitäts-Einstieg bestehen und delegiert auf check_release_system.py.",
        "Damit brechen bestehende lokale Befehle oder ältere Dokumentation nicht abrupt, während neue Testläufe ausschließlich check_release_system.py verwenden können.",
        "Spider-Farmer-, Hardware-, MQTT-, Netzwerk-, Sensor- und UI-Code werden durch CORE.R3.1 nicht verändert.",
    ),
    "tests": (
        "check_release_system.py darf keine feste aktuelle Version wie 3.11.8, 3.11.9 oder eine feste Phase voraussetzen.",
        "Die höchste automatisch entdeckte Version muss GROWSTAR_VERSION, GROWSTAR_INTERNAL_PHASE, current_release() und release_summary() bestimmen.",
        "Release-Dateien und RELEASE_MODULES müssen exakt übereinstimmen.",
        "current.py muss klein und frei von Release-Dictionaries bleiben.",
        "check_release_split.py muss als kompatibler Einstieg denselben permanenten Test ausführen können.",
    ),
}
