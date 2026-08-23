"""Growstar release node 3.11.24 / SF.4D.8."""

RELEASE = {
    "version": "3.11.24",
    "date": "2026-08-23",
    "phase": "SF.4D.8",
    "title": "Bestätigten manuellen Spider-Farmer-Fan-Pfad wiederhergestellt",
    "summary": (
        "SF.4D.8 stellt den auf realer Hardware bereits bestätigten manuellen "
        "Fan-Befehl wieder als privaten Diagnosetest bereit und nutzt denselben "
        "bestätigten Envelope als Fan-only Fallback, wenn im aktuellen Capture "
        "noch kein echtes setConfigField-Template vorhanden ist. Dadurch kann "
        "Growstar den Ventilator nach Bridge-Neustarts weiterhin mit modeType=0, "
        "mOnOff=1 und mLevel L1..L10 ansteuern, ohne dass zuerst in der "
        "Spider-Farmer-App ein Fan-Wert geändert werden muss."
    ),
    "changes": (
        "Private Command-Aktion test_controller_manual_fan wieder verfügbar; kompatibel zum früher erfolgreichen Chat-Hardwaretest mit modeType=0 und mLevel.",
        "Neuer fan-only Compiler erzeugt den real bestätigten DOWN-Topic, keyPath [device, fan] und den minimalen manuellen Fan-Block modeType=0, mOnOff=1, mLevel=N.",
        "Der normale set_controller-Pfad verwendet weiterhin echte beobachtete Templates, solange eines verfügbar ist.",
        "Fehlt für fan ein gültiges Capture-Template, fällt nur die Fan-Familie auf den bestätigten manuellen Envelope zurück; andere Module bleiben unverändert templatepflichtig.",
        "Fan-Level bleibt zentral auf L1 bis L10 begrenzt; der Fallback öffnet keine zweite MQTT-Verbindung und nutzt weiterhin die aktive Controller-Sitzung der Bridge.",
        "Bestehende Minimal-/Powered-Minimal-Diagnosepfade bleiben unverändert erhalten.",
    ),
    "tests": (
        "Regression bestätigt den exakten direkten Manual-Fan-Payload für modeType=0 / mLevel=4.",
        "Regression bestätigt einen Produktions-Fan-Befehl ohne beobachtetes setConfigField-Template mit modeType=0, mOnOff=1 und mLevel=7.",
        "Bestehende Tests für echte Templates, Capture-Rotation, Fan-Grenzen, QoS-0 und Nicht-Fan-Familien bleiben aktiv.",
        "Regression bestätigt, dass test_controller_manual_fan ausschließlich über den bestehenden privaten Command-Socket und die bestehende Controller-MQTT-Sitzung läuft.",
    ),
}
