"""Growstar 3.17.30 / DAILY-TIMER.1 release metadata."""

RELEASE = {
    "version": "3.17.30",
    "date": "2026-09-24",
    "phase": "DAILY-TIMER.1",
    "title": "Zeitschaltuhr mit mehreren täglichen Einschaltfenstern",
    "summary": "Pro Gerät und Station bis zu zwölf wiederkehrende, minutengenaue Zeitfenster mit sicherem AUS dazwischen.",
    "changes": [
        "Neuer Gerätemodus Zeitschaltuhr mit bis zu zwölf unabhängig konfigurierbaren Zeitfenstern pro Tag.",
        "Start inklusive und Ende exklusiv: 21:00 bis 21:03 schaltet drei Minuten EIN.",
        "Mitternacht wird unterstützt; leere, überlappende und ungültige Fenster werden abgelehnt.",
        "AUSSERHALB aller Fenster bleibt das Gerät AUS; Shelly-Sicherheitsbarriere gilt unverändert.",
        "LIVE-Preflight und Watchdog erkennen beschädigte Zeitfenster; der Regelkreis fordert dann AUS an.",
        "Controller-Werte der Zeitschaltuhr sind unabhängig vom bestehenden Zeitmodus.",
        "Bestehende Betriebsarten und Stationspläne bleiben unberührt.",
    ],
    "tests": [
        "python3 tests/regression/check_daily_timer.py",
        "python3 tests/regression/check_interval_day_night.py",
        "python3 tests/regression/check_controller_mode_setpoints.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
