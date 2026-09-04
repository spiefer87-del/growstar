"""Growstar 3.16.13 / VPD.CONTROL.7 release metadata."""

RELEASE = {
    "version": "3.16.13",
    "date": "2026-09-04",
    "phase": "VPD.CONTROL.7",
    "title": "Verbindliche VPD-Feuchtegrenzen",
    "summary": (
        "Tag- und Nacht-Min/Max-Werte der intelligenten VPD-Regelung sind "
        "jetzt harte Feuchtegrenzen. Mathematische VPD-Rechenwerte außerhalb "
        "dieser Spanne werden nicht mehr als Sollwert veröffentlicht."
    ),
    "changes": (
        "VPD_HUM_MIN_DAY, VPD_HUM_MAX_DAY, VPD_HUM_MIN_NIGHT und VPD_HUM_MAX_NIGHT werden als verbindliche Regelgrenzen behandelt.",
        "Der gekoppelte Live-Feuchtesollwert wird immer auf die aktive Tag-/Nacht-Feuchtespanne begrenzt.",
        "Ein höherer oder niedrigerer mathematischer VPD-Feuchtewert bleibt ausschließlich als gekennzeichnete Diagnose im Regellog sichtbar.",
        "Eine gemessene Feuchteüberschreitung bleibt ein aktiver Entfeuchtungsauftrag, auch wenn der VPD bereits sein Zielband erreicht hat.",
        "Eine gemessene Feuchteunterschreitung fordert vorrangig Befeuchtung an und kann keine gegensinnige Entfeuchtung auslösen.",
        "Bei gleichzeitig zu hoher Feuchte und bereits zu hohem VPD bleiben Heizung und Befeuchter gesperrt.",
        "Bei zu hoher Feuchte und zu niedrigem VPD darf die Temperaturreserve nach geeigneter Abluft weiterhin begrenzt helfen.",
        "Sobald die Heizhilfe das VPD-Ziel erreicht, wird sie sofort beendet; eine verbleibende Feuchteüberschreitung geht an den Entfeuchter oder eine sichere Limit-Stufe.",
        "Der Wechsel zwischen Feuchteverletzung und reiner VPD-Abweichung startet den adaptiven 60-Sekunden-Prüftakt neu.",
        "Einstellungen, Profilverwaltung und VPD-Regellog bezeichnen die Temperatur- und Feuchtespannen eindeutig als verbindliche Grenzen.",
        "Es gibt keine Konfigurationsmigration und keine Änderung gespeicherter Werte; vorhandene Min/Max-Werte erhalten lediglich die erwartete verbindliche Bedeutung.",
    ),
    "tests": (
        "python3 tests/regression/check_vpd_hard_humidity_limits.py",
        "python3 tests/regression/check_vpd_coupled_targets.py",
        "python3 tests/regression/check_vpd_heating_after_exhaust.py",
        "python3 tests/regression/check_vpd_adaptive_cadence.py",
        "python3 tests/regression/check_vpd_progressive_escalation.py",
        "python3 tests/regression/check_vpd_intelligent_control.py",
        "python3 tests/regression/check_vpd_ramp_control.py",
        "python3 tests/regression/check_vpd_ramp_ui_independence.py",
        "python3 tests/regression/check_vpd_auto_ui_lock.py",
        "python3 tests/regression/check_vpd_ui_cleanup.py",
        "python3 tests/regression/check_profile_draft_management.py",
        "python3 tests/regression/check_settings_numeric_compatibility.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
