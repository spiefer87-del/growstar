"""Growstar release node 3.11.27 / SF.4D.11."""

RELEASE = {
    "version": "3.11.27",
    "date": "2026-08-23",
    "phase": "SF.4D.11",
    "title": "Spider-Farmer-Blower produktiv über mLevel",
    "summary": (
        "SF.4D.11 übernimmt den am realen GGS-Controller bestätigten Blower-Pfad "
        "in die Growstar-Produktion. Die manuelle Gebläseleistung wird mit "
        "modeType=0, mOnOff=1 und mLevel=25..100 gesendet. Der Growstar-Regler "
        "nutzt dieselbe bestätigte 25-bis-100-Prozent-Skala."
    ),
    "changes": (
        "Produktionsmapping blower.level wird von maxSpeed auf mLevel umgestellt.",
        "Blower wird bei Growstar-Sollwerten explizit in modeType=0 mit mOnOff=1 betrieben.",
        "Alte maxSpeed/minSpeed/Automatikfelder werden nicht aus Capture-Templates zurückgesendet.",
        "Bei fehlendem Capture-Template nutzt Growstar den real bestätigten manuellen Blower-Fallback.",
        "Die zentrale Blower-Skala bleibt bei den hardwarebestätigten 25..100 Prozent.",
        "Der generische Controller-Regler in device_control.html übernimmt min/max automatisch; kein separater UI-Sonderpfad nötig.",
        "Der bestätigte Fan-Level-/Shake-Pfad bleibt unverändert.",
    ),
    "tests": (
        "check_spiderfarmer_manual_blower.py prüft den bestätigten mLevel-Payload und den Produktions-Fallback.",
        "check_spiderfarmer_command_path.py prüft blower.level über mLevel neben dem bestehenden Fan-Pfad.",
        "Realer Produktionstest: Growstar-Regler für Gebläse auf 40, 70 und 25 Prozent stellen und Hardware-Reaktion prüfen.",
    ),
}
