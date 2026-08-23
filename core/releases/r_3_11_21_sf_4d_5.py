"""Growstar release node 3.11.21 / SF.4D.5."""

RELEASE = {
    "version": "3.11.21",
    "date": "2026-08-23",
    "phase": "SF.4D.5",
    "title": "Powered-Minimal-Fan-Test mit mOnOff und einem Sollwert",
    "summary": (
        "Der SF.4D.4-Minimaltest mit ausschließlich maxSpeed schaltete den "
        "Spider-Farmer-Fan intern aus. SF.4D.5 prüft deshalb als nächsten "
        "kleinstmöglichen Schritt einen Fan-Block aus mOnOff=1 plus exakt einem "
        "Growstar-Sollwert."
    ),
    "changes": (
        "Der normale set_controller-Pfad bleibt unverändert.",
        "Der Diagnose-Test sendet mOnOff=1 plus genau maxSpeed oder shakeLevel.",
        "Intervall-, Standby-, Natural-Wind-, Zeitplan- und weitere Fan-Felder werden nicht mitgesendet.",
        "Die zentrale L1-bis-L10-Validierung bleibt aktiv.",
    ),
}
