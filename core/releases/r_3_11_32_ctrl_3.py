"""Growstar release node 3.11.32 / CTRL.3."""

RELEASE = {
    "version": "3.11.32",
    "date": "2026-08-23",
    "phase": "CTRL.3",
    "title": "Controller-Sollwerte getrennt pro Betriebsmodus",
    "summary": (
        "CTRL.3 entfernt den bisherigen globalen Controller-Slider aus dem "
        "Kopfbereich der Geräteansicht. Dauerbetrieb, Zeitsteuerung, Intervall "
        "A/B und ENV besitzen nun jeweils eigene Controller-Sollwerte. OFF "
        "besitzt bewusst keine Controllerwerte. Shelly bleibt unverändert die "
        "harte Autorität über das physische Ein- und Ausschalten."
    ),
    "changes": (
        "Controller-Kopfkarte zeigt nur noch Zuordnung, Status und Sicherheitsinformation.",
        "Dauerbetrieb besitzt einen eigenen Controller-Zustand on.",
        "Zeitsteuerung besitzt einen eigenen Controller-Zustand time.",
        "Intervall A und B behalten ihre getrennten Controller-Zustände.",
        "ENV besitzt einen eigenen Controller-Zustand env.",
        "OFF besitzt keine Controller-Sollwerte und sendet weiterhin niemals Controllerbefehle.",
        "Alte params.controller-Werte bleiben als Migrations-Fallback erhalten.",
        "Beim Speichern wird kein globaler controller_setpoints-Befehl mehr unmittelbar gesendet.",
        "ENV nutzt seinen festen Modus-Sollwert solange die Umgebungsbedingung aktiv ist; eine spätere proportionale Regelung kann ihn dynamisch ersetzen.",
    ),
    "tests": (
        "check_controller_states.py bleibt als Shelly-Prioritätsregression bestehen.",
        "check_controller_interval_ui.py bleibt als Intervall-UI-Regression bestehen.",
        "check_controller_mode_setpoints.py prüft eigene Zustände für ON, TIME, ENV und INTERVAL sowie Legacy-Fallback und OFF-Sicherheit.",
    ),
}
