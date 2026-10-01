"""Growstar 3.17.36 / ENV.HUM.HYSTERESIS.1 release metadata."""

RELEASE = {
    "version": "3.17.36",
    "date": "2026-10-01",
    "phase": "ENV.HUM.HYSTERESIS.1",
    "title": "ENV-Feuchteregelung beendet den Zyklus am Sollwert",
    "summary": "Toleranz startet Be- oder Entfeuchtung; der aktive Zyklus endet am Sollwert.",
    "changes": [
        "Klassischer ENV-Entfeuchter startet oberhalb Soll plus Toleranz und läuft bis zum Sollwert.",
        "Klassischer ENV-Befeuchter startet unterhalb Soll minus Toleranz und läuft bis zum Sollwert.",
        "Die Regelung verwendet den tatsächlich bestätigten Relaiszustand beziehungsweise SHADOW-Ausgang als Hysterese-Gedächtnis.",
        "Ohne Messwert endet der Auftrag; Fan-Standby, VPD-AUTO und andere Betriebsarten bleiben unabhängig.",
        "Kein neues Konfigurationsfeld und keine Datenbankmigration.",
    ],
    "tests": [
        "python3 tests/regression/check_env_humidity_hysteresis.py",
        "python3 tests/regression/check_fan_env_standby.py",
        "python3 tests/regression/check_vpd_intelligent_control.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
