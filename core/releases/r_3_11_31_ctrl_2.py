"""Growstar release node 3.11.31 / CTRL.2."""

RELEASE = {
    "version": "3.11.31",
    "date": "2026-08-23",
    "phase": "CTRL.2",
    "title": "Intervallzustände A/B in der Geräteansicht",
    "summary": (
        "CTRL.2 macht das in CTRL.1 eingeführte Zustandsmodell in der "
        "Geräteansicht konfigurierbar. Intervallbetrieb besitzt nun Phase A "
        "und Phase B mit jeweils eigener Dauer, eigener Shelly-Power und "
        "eigenen Controller-Sollwerten. Shelly bleibt unverändert die harte "
        "Power-Autorität."
    ),
    "changes": (
        "Intervallzeiten werden in der UI komfortabel in Minuten eingegeben und intern weiter als Sekunden gespeichert.",
        "Phase A besitzt eine eigene Shelly-Power-Auswahl und eigene Controller-Werte.",
        "Phase B besitzt eine eigene Shelly-Power-Auswahl und eigene Controller-Werte.",
        "Bestehende Konfigurationen bleiben kompatibel: Phase A standardmäßig EIN, Phase B standardmäßig AUS.",
        "Bei Power AUS werden die Controller-Felder der jeweiligen Phase ausgeblendet und leer gespeichert.",
        "Der bisherige Controller-Regler bleibt als Dauerbetrieb-/Standardwert erhalten.",
        "Die UI weist ausdrücklich darauf hin, dass Shelly beim Ausschalten immer Vorrang besitzt.",
        "Keine Änderung am bereits getesteten CTRL.1-Regelkern.",
    ),
    "tests": (
        "check_controller_interval_ui.py prüft A/B-Power, getrennte Controllerfelder, Minutenumrechnung und Shelly-Hinweis.",
        "Manueller UI-Test: Ventilator INTERVAL auf 15 min L7 und 10 min L3 konfigurieren.",
        "Rückwärtskompatibilität prüfen: Phase B AUS muss klassisches EIN/AUS-Intervall ergeben.",
    ),
}
