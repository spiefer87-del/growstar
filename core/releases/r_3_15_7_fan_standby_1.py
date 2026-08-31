"""Growstar 3.15.7 / FAN.STANDBY.1 release metadata."""

RELEASE = {
    "version": "3.15.7",
    "date": "2026-08-31",
    "phase": "FAN.STANDBY.1",
    "title": "ENV-Lüfter mit Standby-Grundlüftung",
    "summary": (
        "Der Abluft-Lüfter kann im Umgebungsmodus bei normalen Umweltwerten "
        "mit einer separat einstellbaren Standby-Leistung weiterlaufen."
    ),
    "changes": (
        "Neuer opt-in Control-State env_standby für den Abluft-Lüfter.",
        "Bei Regelbedarf bleibt die bestehende ENV-Regelleistung aktiv.",
        "Sind alle ausgewählten Umweltwerte im Sollbereich, kann Standby aktiv bleiben.",
        "Ohne aktiviertes Standby bleibt das bisherige ENV-zu-AUS-Verhalten erhalten.",
        "Fehlende ausgewählte Sensorwerte führen sicher zu AUS und niemals zu Standby.",
        "Standby ist nur mit zugewiesenem Controller und regelbarer Leistung aktivierbar.",
        "Die Geräteoberfläche besitzt getrennte Regelleistung und Standby-Leistung.",
        "Das Dashboard kennzeichnet Regelung und Standby getrennt.",
        "Shelly bleibt unverändert Power-Master; Controllerwerte umgehen den Power-Pfad nicht.",
    ),
    "tests": (
        "python3 tests/regression/check_fan_env_standby.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
