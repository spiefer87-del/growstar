"""Growstar release node 3.11.22 / SF.4D.6."""

RELEASE = {
    "version": "3.11.22",
    "date": "2026-08-23",
    "phase": "SF.4D.6",
    "title": "Spider-Farmer-Ventilator auf bestätigten manuellen Laufzeitpfad umgestellt",
    "summary": (
        "Reale Schreibtests am GGS-Controller haben die Ventilator-Semantik "
        "eindeutig geklärt: modeType=1 schaltet in den Zeitfenstermodus, während "
        "modeType=0 zusammen mit mOnOff=1 den manuellen Betrieb auswählt. mLevel "
        "setzt dabei direkt die sichtbare Stufe L1 bis L10. SF.4D.6 übernimmt "
        "diese bestätigte Semantik in den normalen Growstar-Schreibpfad und "
        "beendet das Zurücksenden alter Spider-Farmer-Zeit-/Zykluskonfiguration."
    ),
    "changes": (
        "Fan-Level wird im Spider-Farmer-Command-Modell von maxSpeed auf das real bestätigte mLevel umgestellt.",
        "Der normale set_controller-Pfad sendet für fan immer modeType=0 und mOnOff=1 plus ausschließlich die angeforderten Growstar-Fan-Sollwerte.",
        "Ein Growstar-Fan-Level 4 erzeugt damit modeType=0, mOnOff=1, mLevel=4; Level 7 entsprechend mLevel=7.",
        "Beobachtete timePeriod-, cycleTime-, minSpeed-, maxSpeed-, natural- und sonstige Spider-Farmer-Fan-Konfiguration wird im Produktionspfad nicht mehr zurückgesendet.",
        "Oszillation bleibt als Growstar-Sollwert auf shakeLevel abgebildet und wird nur gesendet, wenn sie im Request enthalten ist.",
        "Licht und Gebläse behalten ihren bisherigen beobachteten Template-Pfad unverändert bei.",
        "Der bestehende private Command-Socket, die aktive Controller-MQTT-Sitzung, QoS 0 und der Provider-Adapter bleiben unverändert.",
        "Power EIN/AUS bleibt weiterhin getrennt beim Growstar-Power-Aktor; mOnOff=1 aktiviert ausschließlich den internen Fan-Laufzeitpfad des Controllers.",
        "Die historischen SF.4D.4/SF.4D.5 Diagnosepfade bleiben getrennt vom Produktionspfad erhalten.",
    ),
    "tests": (
        "Realer Controller-Test: modeType=1 und mLevel=4 führte sichtbar zum Zeitfenstermodus und bestätigte, dass modeType=1 nicht Dauerbetrieb ist.",
        "Realer Controller-Test: modeType=0, mOnOff=1 und mLevel=4 führte sichtbar zu L4 / Manueller.",
        "Realer Controller-Test: modeType=0, mOnOff=1 und mLevel=7 führte sichtbar zu L7 / Manueller.",
        "check_spiderfarmer_command_path.py prüft den exakten Produktions-Fanblock modeType=0, mOnOff=1, mLevel und optional shakeLevel.",
        "Die Regression prüft, dass Zeitfenster-, Zyklus-, Natural-Wind-, minSpeed- und maxSpeed-Felder nicht mehr aus einem beobachteten Fan-Template zurückgesendet werden.",
        "Ungültige Fan-Level außerhalb L1 bis L10 bleiben an der zentralen Schema- und Bridge-Grenze blockiert.",
        "Capture-Rotation, echtes DOWN-Topic/keyPath, MQTT-QoS-0 und die unveränderten Licht-/Gebläsepfade bleiben regressionsgesichert.",
        "check_spiderfarmer_powered_minimal_write.py folgt der korrigierten Level-Zuordnung mLevel, bleibt aber ausdrücklich ein Diagnosepfad.",
    ),
}
