"""Growstar release node 3.11.18 / SF.4D.2."""

RELEASE = {
    "version": "3.11.18",
    "date": "2026-08-23",
    "phase": "SF.4D.2",
    "title": "Spider-Farmer Command-Templates über Capture-Rotation hinweg erhalten",
    "summary": (
        "Der SF.4D-Schreibpfad verwendet weiterhin ausschließlich real beobachtete "
        "DOWN/setConfigField-Pakete als Vorlage. Die Diagnose-Capture rotiert jedoch "
        "bewusst von raw_frames.jsonl nach raw_frames.jsonl.1. Dadurch konnte ein "
        "gültiges älteres Controller-Template nach einer Rotation nicht mehr gefunden "
        "werden, obwohl es noch auf der Platte vorhanden war. SF.4D.2 erweitert nur "
        "die bestehende Template-Suche auf die bereits vorhandene rotierte Capture-Datei."
    ),
    "changes": (
        "command_model.py durchsucht zuerst raw_frames.jsonl und anschließend raw_frames.jsonl.1.",
        "Die aktuelle Capture-Generation behält immer Vorrang vor der älteren Rotation.",
        "Es wird weiterhin kein undocumented Spider-Farmer-Payload erfunden.",
        "Nur echte DOWN/setConfigField-Templates mit passender Controller-PID und passendem Modul werden akzeptiert.",
        "MQTT-, Command-Socket-, Provider-, Sensor- und Netzwerkpfade bleiben unverändert.",
        "Die bestehende Diagnose-Rotation bleibt aktiv und begrenzt die Capture-Größe weiterhin wie vorgesehen.",
    ),
    "tests": (
        "check_spiderfarmer_command_path.py prüft den bisherigen normalen Template-Fall unverändert weiter.",
        "Neu wird geprüft, dass ein Fan-Template aus raw_frames.jsonl.1 nach Rotation gefunden wird.",
        "Neu wird geprüft, dass ein neueres Template in raw_frames.jsonl Vorrang vor raw_frames.jsonl.1 hat.",
        "Die bisherigen QoS-0-, Decoder-, Command-Socket- und Provider-Grenzen bleiben vollständig erhalten.",
    ),
}
