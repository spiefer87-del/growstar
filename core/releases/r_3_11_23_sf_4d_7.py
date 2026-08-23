"""Growstar release node 3.11.23 / SF.4D.7."""

RELEASE = {
    "version": "3.11.23",
    "date": "2026-08-23",
    "phase": "SF.4D.7",
    "title": "Spider-Farmer-Produktionspfad kontrolliert end-to-end testbar",
    "summary": (
        "SF.4D.7 ergänzt keinen zweiten Steuerpfad, sondern ein bewusst "
        "abgesichertes Testwerkzeug für den bereits vorhandenen Growstar-"
        "Produktionsweg. Der Test läuft über die normale Geräte-HTTP-API, "
        "prüft zuerst die reale Controller-Zuordnung und das zentrale "
        "Sollwertschema und darf erst mit --yes einen echten Sollwert senden. "
        "Damit kann die Kette Growstar-Geräte-API -> Provider-Adapter -> "
        "bestehende Spider-Farmer-Bridge -> bestehende Controller-MQTT-Sitzung "
        "geprüft werden, ohne den Diagnose-Command-Socket direkt anzusprechen."
    ),
    "changes": (
        "Neues Tool tools/test_spiderfarmer_production_setpoint.py für einen kontrollierten echten Produktionspfad-Test.",
        "Dry-Run ist Standard; ein realer Controller-Schreibvorgang benötigt ausdrücklich --yes.",
        "Vor jedem Schreibtest wird das bestehende Growstar-Geräte-GET ausgewertet und Controller-Zuordnung, Provider, Familie und zentrales L1-bis-L10-Schema geprüft.",
        "Das Tool sendet ausschließlich generische controller_setpoints an die bestehende Tent-Geräte-API und kennt weder MQTT-Pakete noch setConfigField noch den privaten UNIX-Command-Socket.",
        "Level kann allein getestet werden; Oszillation wird nur verändert, wenn --oscillation ausdrücklich angegeben wird.",
        "Der bestehende controller_apply-Rückkanal der Geräte-API wird ausgewertet und Bridge-Fehler führen zu einem fehlgeschlagenen Test.",
        "Keine Änderung an Power-Schaltung, Regelkreis, Spider-Farmer-Command-Compiler oder MQTT-Transport.",
    ),
    "tests": (
        "Neue Offline-Regression check_spiderfarmer_production_setpoint_tool.py prüft URL, Preflight, L1-bis-L10-Grenzen und exakten generischen API-Payload.",
        "Regression stellt sicher, dass das Tool weder command.sock, setConfigField, MQTT-Paketbau noch compile_controller_command direkt verwendet.",
        "Regression bestätigt, dass routes/device.py weiterhin den bestehenden send_controller_setpoints-Adapter mit requested_setpoints verwendet.",
        "Regression bestätigt, dass services/spiderfarmer_commands.py weiterhin den einzigen set_controller-Produktionsadapter bereitstellt.",
        "Der reale Hardwaretest bleibt bewusst separat: zunächst Dry-Run, anschließend derselbe Befehl mit --yes und Kontrolle in der Spider-Farmer-App.",
    ),
}
