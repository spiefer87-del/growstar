"""Growstar release node 3.11.34 / CTRL.3.2."""

RELEASE = {
    "version": "3.11.34",
    "date": "2026-08-23",
    "phase": "CTRL.3.2",
    "title": "Controller-Level nach Growstar-Neustart wieder freigeben",
    "summary": (
        "CTRL.3.2 korrigiert die Power-Freigabe des neuen Controller-"
        "Zustandsmodells. Nach einem Growstar-Neustart konnte der physische "
        "Shelly bereits EIN sein, während das flüchtige Runtime-Bit noch AUS "
        "meldete. Dadurch wurden Ventilator- und Gebläse-Level blockiert. "
        "Growstar akzeptiert nun zusätzlich einen frischen, verifizierten "
        "read-only Shelly-Hardwarestatus als EIN-Bestätigung."
    ),
    "changes": (
        "Controllerwrites bleiben weiterhin grundsätzlich an einen angeforderten Power-EIN-Zustand gebunden.",
        "Das Runtime-Powerbit bleibt der schnelle primäre Freigabepfad.",
        "Ist das Runtime-Bit nach Neustart noch AUS, darf ein frischer actuator_health-Eintrag mit state=ok und actual_state=true den Controllerwrite freigeben.",
        "Der neue Fallback verwendet ausschließlich den vorhandenen read-only Shelly-Health-Cache und erzeugt keinen zusätzlichen Netzwerkzugriff.",
        "Shelly-Power AUS bleibt hart autoritativ und sendet weiterhin niemals einen Controller-Level-Befehl.",
        "Unbekannter, stale, offline oder tatsächlich AUS gemeldeter Shelly-Zustand blockiert weiterhin jeden Controllerwrite.",
        "Keine Änderung an Spider-Farmer-Payloads oder Modus-Sollwerten.",
    ),
    "tests": (
        "check_controller_states.py bleibt als Grundregression der Shelly-Priorität bestehen.",
        "check_controller_power_gate.py prüft Runtime-EIN, verifiziertes Hardware-EIN, Hardware-AUS und Power-AUS.",
        "Nach Installation Ventilator und Gebläse im Dauerbetrieb über ihre Modus-Slider testen.",
    ),
}
