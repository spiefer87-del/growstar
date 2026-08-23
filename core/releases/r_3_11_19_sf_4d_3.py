"""Growstar release node 3.11.19 / SF.4D.3."""

RELEASE = {
    "version": "3.11.19",
    "date": "2026-08-23",
    "phase": "SF.4D.3",
    "title": "Spider-Farmer Fan-Sollwerte am finalen Schreibpfad auf L1 bis L10 absichern",
    "summary": (
        "Der erste echte Growstar-Schreibtest hat bestätigt, dass Spider Farmer "
        "maxSpeed direkt als Ventilatorstufe interpretiert: der Testwert 60 wurde "
        "in der App tatsächlich als L60 sichtbar. Die Geräte-UI und die normale "
        "Geräte-API modellierten Fan-Level und Oszillation bereits korrekt als "
        "L1 bis L10. SF.4D.3 zieht dieselbe zentrale Schema-Validierung nun bis an "
        "die finale Bridge-Schreibgrenze, damit auch direkte oder manipulierte "
        "Command-Socket-Aufrufe keinen unzulässigen Fan-Wert senden können."
    ),
    "changes": (
        "core/controller_setpoints.py stellt das bestehende Familienschema zusätzlich direkt als gemeinsame Schemaquelle bereit.",
        "Fan-Level und Fan-Oszillation bleiben strikt L1 bis L10.",
        "Licht und Gebläse behalten unabhängig davon ihre bestehende 0-bis-100-Skala.",
        "command_model.py normalisiert jeden Controller-Sollwert vor dem Erzeugen eines Spider-Farmer-PUBLISH über dieselbe zentrale Schemaquelle.",
        "Direkte Command-Socket-Aufrufe können dadurch Fan-Werte wie 0, 11 oder 60 nicht mehr an den Controller senden.",
        "Beobachtete Fan-Templates mit bereits ungültigen Growstar-eigenen Werten werden nicht wiederverwendet; die Suche fällt auf das nächste gültige echte Template zurück.",
        "MQTT-Paketformat, Command-Socket, Netzwerk, Sensorik, Power-Aktoren und die beobachtete Template-Architektur bleiben unverändert.",
    ),
    "tests": (
        "check_controller_setpoints.py prüft die gemeinsame zentrale Fan-Schemaquelle und blockiert ausdrücklich L60.",
        "check_controller_setpoints.py bestätigt weiterhin, dass 60 für Licht und Gebläse gültig bleibt.",
        "check_spiderfarmer_command_path.py blockiert ungültige Fan-Werte direkt an der Bridge-Schreibgrenze.",
        "check_spiderfarmer_command_path.py prüft, dass ein historisches ungültiges L60-Template übersprungen und ein älteres gültiges echtes Template verwendet wird.",
        "Capture-Rotation, QoS-0-PUBLISH, Decoder- und Provider-Grenzen bleiben regressionsgesichert.",
    ),
}
