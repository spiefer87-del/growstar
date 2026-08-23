"""Growstar release node 3.11.20 / SF.4D.4."""

RELEASE = {
    "version": "3.11.20",
    "date": "2026-08-23",
    "phase": "SF.4D.4",
    "title": "Isolierter Minimal-Schreibtest für Spider-Farmer-Fan",
    "summary": (
        "Der produktive SF.4D-Schreibpfad sendet derzeit einen vollständigen "
        "historisch beobachteten Fan-Konfigurationsblock. Dadurch kann ein reiner "
        "Gangwechsel ältere Intervall-, Standby- oder Natural-Wind-Einstellungen "
        "zurückschreiben. SF.4D.4 führt ausschließlich für einen kontrollierten "
        "Diagnosetest eine getrennte private Minimal-Write-Action ein."
    ),
    "changes": (
        "Der normale set_controller-Pfad bleibt vollständig unverändert.",
        "test_controller_minimal ist nur über den privaten UNIX-Command-Socket erreichbar.",
        "Das Minimalpaket erhält den real beobachteten DOWN-Topic, äußeren setConfigField-Envelope und keyPath.",
        "Im Modulblock wird ausschließlich der explizit angeforderte Growstar-Sollwert gesendet.",
        "Fan-Level/Oszillation bleiben an der finalen Schreibgrenze L1 bis L10 validiert.",
        "Das mitgelieferte Tool verlangt --yes und erlaubt pro Test genau einen Sollwert.",
        "Es wird kein zweiter MQTT-Client und kein neuer HTTP-Schreibpfad eingeführt.",
    ),
    "tests": (
        "check_spiderfarmer_minimal_write.py beweist, dass bei level nur maxSpeed im fan-Block verbleibt.",
        "Der Test beweist, dass modeType, cycleTime, timePeriod und natural nicht mitgesendet werden.",
        "L60 bleibt auch im Diagnosepfad blockiert.",
    ),
}
