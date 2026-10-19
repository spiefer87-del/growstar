"""Growstar 3.17.47 / SENSOR.FALLBACK.ALERTS.1."""

RELEASE = {
    "version": "3.17.47",
    "date": "2026-10-19",
    "phase": "SENSOR.FALLBACK.ALERTS.1",
    "title": "Watchdog und Telegram melden Sensor-Fallbacks",
    "summary": "Umschaltung, Totalausfall und Rückkehr zum Primärsensor erhalten passende Warnungen.",
    "changes": [
        "Watchdog zeigt den aktiven Ersatzsensor, seinen Zustand und die Umschaltzeit je Station.",
        "Telegram sendet eine eigene, abschaltbare Fallback-Meldung und nach Rückkehr eine Entwarnung.",
        "Fallen beide Innenquellen aus, greift der bestehende Sensoralarm ohne falsche Entwarnung.",
        "Bei optionalen Messgrößen werden zwei ausgefallene zugewiesene Quellen ebenfalls gemeldet.",
        "Die unvollständige Watchdog-Vorlage wird wieder vollständig renderbar gemacht.",
    ],
    "tests": [
        "python3 tests/regression/check_sensor_fallback_alerts.py",
        "python3 tests/regression/check_sensor_fallback.py",
        "python3 tests/regression/check_notifications.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
