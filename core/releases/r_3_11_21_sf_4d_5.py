"""Growstar release node 3.11.21 / SF.4D.5."""

RELEASE = {
    "version": "3.11.21",
    "date": "2026-08-23",
    "phase": "SF.4D.5",
    "title": "Powered-Minimal-Fan-Protokolltest",
    "summary": (
        "Der SF.4D.4-Minimaltest mit ausschließlich maxSpeed änderte den "
        "Controllerzustand unerwünscht auf Fan AUS. SF.4D.5 testet deshalb "
        "isoliert die nächstkleinere bekannte Pflichtmenge: mOnOff=1 plus "
        "exakt einen Growstar-Fan-Sollwert."
    ),
    "changes": (
        "Die hochgeladene und bestätigte SF.4D.4 command_proxy.py ist die direkte Patch-Basis.",
        "Der normale set_controller-Produktionspfad bleibt unverändert.",
        "Der bestehende SF.4D.4 test_controller_minimal-Pfad bleibt erhalten.",
        "Neue private Action test_controller_minimal_powered ist ausschließlich für fan zulässig.",
        "Der Diagnoseblock enthält mOnOff=1 plus genau maxSpeed oder shakeLevel.",
        "modeType, minSpeed, Natural Wind, Zeitpläne, Cycle- und Standby-Felder werden nicht mitgesendet.",
        "Fan-Sollwerte bleiben an der finalen Grenze strikt L1 bis L10.",
        "Kein neuer MQTT-Client und kein neuer HTTP-Schreibpfad werden eingeführt.",
    ),
    "tests": (
        "check_spiderfarmer_powered_minimal_write.py prüft den exakten Fan-Payload.",
        "Der Test schützt den Produktionspfad und SF.4D.4 vor versehentlicher Entfernung.",
        "L0, L11, L60 und Mehrfach-Sollwerte werden geblockt.",
    ),
}
