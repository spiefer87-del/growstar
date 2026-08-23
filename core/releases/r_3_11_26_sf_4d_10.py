"""Growstar release node 3.11.26 / SF.4D.10."""

RELEASE = {
    "version": "3.11.26",
    "date": "2026-08-23",
    "phase": "SF.4D.10",
    "title": "Spider-Farmer-Blower testet mLevel statt maxSpeed",
    "summary": (
        "SF.4D.10 reagiert auf den realen Hardwarebefund aus SF.4D.9: "
        "modeType=0 schaltet den Blower korrekt in den manuellen Modus, "
        "maxSpeed verändert die tatsächliche Leistung aber nicht. Der isolierte "
        "Blower-Test sendet deshalb jetzt mLevel und verwendet die in der "
        "Spider-Farmer-App beobachtete manuelle Range 25 bis 100 Prozent."
    ),
    "changes": (
        "Der private Befehl test_controller_manual_blower bleibt erhalten.",
        "Der Diagnose-Payload sendet modeType=0, mOnOff=1 und mLevel=25..100.",
        "maxSpeed wird im Diagnosepfad nicht mehr als manueller Leistungswert verwendet.",
        "Die zentrale Growstar-Blower-Skala wird auf die beobachtete Range 25..100 Prozent korrigiert.",
        "Der bereits bestätigte Fan-Pfad SF.4D.8 bleibt unverändert.",
        "Das Produktionsmapping blower.level -> maxSpeed bleibt absichtlich noch unverändert, bis mLevel am realen Blower bestätigt ist.",
    ),
    "tests": (
        "Regression check_spiderfarmer_manual_blower.py prüft mLevel-Payload, DOWN-Topic und 25..100-Grenzen.",
        "Regression bestätigt zusätzlich, dass das Produktionsmapping vor der Hardwarebestätigung nicht vorzeitig umgestellt wird.",
        "Realer Hardwaretest: mLevel=40, danach 70 und 25 senden und die tatsächliche Gebläseleistung beobachten.",
    ),
}
