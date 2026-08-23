"""Growstar release node 3.11.25 / SF.4D.9."""

RELEASE = {
    "version": "3.11.25",
    "date": "2026-08-23",
    "phase": "SF.4D.9",
    "title": "Spider-Farmer-Blower für kontrollierten manuellen Hardwaretest vorbereitet",
    "summary": (
        "SF.4D.9 überträgt das beim Ventilator erfolgreiche Diagnoseprinzip auf "
        "den Spider-Farmer-Blower. Growstars bereits bestehendes Blower-Schema "
        "bleibt 0 bis 100 Prozent und wird auf maxSpeed abgebildet. Der neue "
        "private Testpfad sendet modeType=0, mOnOff=1 und maxSpeed, bleibt aber "
        "bis zur realen Hardwarebestätigung bewusst vom Produktions-Fallback getrennt."
    ),
    "changes": (
        "Neuer privater Command-Socket-Befehl test_controller_manual_blower.",
        "Blower-Test verwendet das bestehende DOWN-Topic und keyPath ['device', 'blower'].",
        "Manueller Kandidat sendet ausschließlich modeType=0, mOnOff=1 und maxSpeed=0..100.",
        "Die zentrale Growstar-Blower-Skala 0..100 bleibt unverändert und wird zusätzlich validiert.",
        "Der bereits bestätigte Fan-Pfad SF.4D.8 bleibt unverändert.",
        "Der normale Blower-Produktionspfad bleibt bis zur Hardwarebestätigung templatebasiert; kein unbestätigter Fallback wird aktiviert.",
    ),
    "tests": (
        "Neue Regression check_spiderfarmer_manual_blower.py prüft Payload, Topic, 0..100-Grenzen und Socket-Registrierung.",
        "Bestehende Spider-Farmer-Command-Regression bleibt unverändert lauffähig.",
        "Realer Hardwaretest: zunächst maxSpeed=40 über test_controller_manual_blower senden und die tatsächliche Abluftleistung beobachten.",
    ),
}
