"""Growstar 3.16.12 / VPD.CONTROL.6 release metadata."""

RELEASE = {
    "version": "3.16.12",
    "date": "2026-09-04",
    "phase": "VPD.CONTROL.6",
    "title": "Adaptive VPD-Wirkungsprüfung",
    "summary": (
        "Die intelligente VPD-Regelung reagiert nach Starts und neuen "
        "Abweichungen bereits nach 60 Sekunden, beruhigt träge Reaktionen "
        "über 120 Sekunden und nutzt den längeren konfigurierten Prüftakt "
        "erst nach zehn stabilen Minuten."
    ),
    "changes": (
        "Die VPD-Sensorwerte, das Zielband und alle Safety-Grenzen werden weiterhin in jedem normalen Hauptzyklus geprüft.",
        "Nur die Freigabe der jeweils nächsten Aktorstufe verwendet ein adaptives Wirkungsfenster.",
        "Eine neue Strategie, neue Aktorstufe oder deutliche VPD-Abweichung startet mit einer 60-Sekunden-Schnellprüfung.",
        "Nahe am Ziel sowie bei einer noch nicht eindeutig reagierenden Heizstufe folgt eine 120-Sekunden-Beruhigungsphase.",
        "Erst nach zehn Minuten durchgehend im VPD-Zielband wird auf den konfigurierten maximalen Stabiltakt gewechselt.",
        "Der vorhandene Wert VPD_EFFECT_WINDOW_MIN bleibt erhalten und bildet jetzt die Obergrenze des adaptiven Takts; Standard bleiben fünf Minuten.",
        "Wird das VPD-Zielband erreicht, beendet der Koordinator die Eskalation sofort und wartet nicht auf den Ablauf eines Wirkungsfensters.",
        "Bei einer erneuten Abweichung oder einem Strategiewechsel fällt der Takt automatisch wieder auf 60 Sekunden zurück.",
        "Pro abgelaufenem Wirkungsfenster bleibt höchstens ein Aktorschritt zulässig, damit Abluft und Heizung nicht sprunghaft eskalieren.",
        "Regellog und Einstellungsseite zeigen bzw. erklären Schnellprüfung, Beruhigungsphase, Stabilbetrieb und die nächste Stufenprüfung.",
        "Es gibt keine Konfigurationsmigration und keine Änderung gespeicherter Profile, Sensorzuweisungen oder Gerätesollwerte.",
    ),
    "tests": (
        "python3 tests/regression/check_vpd_adaptive_cadence.py",
        "python3 tests/regression/check_vpd_heating_after_exhaust.py",
        "python3 tests/regression/check_vpd_coupled_targets.py",
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
