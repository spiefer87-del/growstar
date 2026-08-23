"""Growstar release node 3.11.30 / CTRL.1."""

RELEASE = {
    "version": "3.11.30",
    "date": "2026-08-23",
    "phase": "CTRL.1",
    "title": "Regelzustände mit harter Shelly-Priorität",
    "summary": (
        "CTRL.1 legt das Fundament für leistungsabhängige Dauer-, Zeit- und "
        "Intervallregelung. Ein Regelzustand besteht künftig aus physischer "
        "Power und optionalen Controller-Sollwerten. Shelly bleibt dabei die "
        "harte Power-Autorität: Ein AUS-Zustand sendet niemals Controllerwerte, "
        "und ein Controller kann eine durch Shelly/Safety/Shadow blockierte "
        "Powerfreigabe nicht umgehen."
    ),
    "changes": (
        "Neues provider-neutrales Zustandsmodell core/controller_states.py.",
        "Dauerbetrieb verwendet weiterhin params.controller als rückwärtskompatiblen Standard-Sollwert.",
        "TIME verwendet den Dauerbetriebszustand innerhalb des Zeitfensters und einen harten OFF-Zustand außerhalb.",
        "INTERVAL löst künftig Phase A und Phase B als getrennte Regelzustände auf.",
        "Bestehende Intervalle bleiben unverändert kompatibel: Phase A EIN, Phase B AUS.",
        "Optional kann control_states.interval_b später Power EIN plus eigenen Controller-Level erhalten.",
        "Controller-Kommandos werden bei physischem/logischem Power AUS grundsätzlich übersprungen.",
        "Controller-Kommandos werden nicht gesendet, wenn der bestehende Shelly-/Safety-/Shadow-Pfad EIN nicht freigibt.",
        "ENV bleibt in CTRL.1 bewusst unverändert und wird in einer späteren Phase auf variable Leistungsregelung erweitert.",
    ),
    "tests": (
        "check_controller_states.py prüft Dauerzustand, Intervall A/B und Rückwärtskompatibilität.",
        "Regression bestätigt: OFF erzeugt nur Shelly AUS und niemals einen Controller-Level-Befehl.",
        "Regression bestätigt: blockierte Shelly-/Safety-Power kann nicht durch den Controller umgangen werden.",
    ),
}
