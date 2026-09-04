"""Growstar 3.16.6 / VPD.UI.1 release metadata."""

RELEASE = {
    "version": "3.16.6",
    "date": "2026-09-04",
    "phase": "VPD.UI.1",
    "title": "Eigenständige VPD-Rampe und eindeutige AUTO-Bedienung",
    "summary": (
        "Die VPD-Rampe ist nun direkt bei der intelligenten Regelung sichtbar "
        "und bleibt vollständig von Helligkeitssensor und Sonnenverlauf "
        "unabhängig. In AUTO werden klassische Klima-Sollwerte sichtbar gesperrt."
    ),
    "changes": (
        "VPD-Rampenschalter und Rampenzeit stehen direkt im Bereich Intelligente VPD-Steuerung.",
        "Die Profilverwaltung zeigt dieselbe Rampeneinstellung unmittelbar beim VPD-Profil.",
        "Die VPD-Rampe benötigt weder einen Helligkeitssensor noch einen Lichtcontroller.",
        "Der Sonnenverlauf behält seinen eigenen Schalter sowie eigene Auf- und Untergangsdauern.",
        "Morgens beginnt die VPD-Rampe exakt bei Tag Start und endet nach ihrer eigenen Dauer.",
        "Abends beginnt die VPD-Rampe um ihre eigene Dauer vor Nacht Start und endet exakt bei Nacht Start.",
        "Eine neue Vorschau zeigt beide tatsächlichen Rampenfenster als Uhrzeiten.",
        "AUTO sperrt und dimmt klassische Tag-/Nacht-Sollwerte sowie deren Regel-Toleranzen.",
        "OFF und MONITOR lassen die klassischen Sollwerte weiterhin vollständig bearbeitbar.",
        "Alarm-Toleranzen und absolute Schutzgrenzen bleiben auch in AUTO bearbeitbar.",
        "Gesperrte Fallback-Werte werden beim Speichern unverändert erhalten und nicht gelöscht.",
        "Eine vorhandene Rampendauer 0 bleibt bei ausgeschalteter Rampe gültig; aktiv sind weiterhin mindestens fünf Minuten erforderlich.",
        "Es gibt keine neuen Konfigurationsfelder und keine Migration vorhandener Profile.",
    ),
    "tests": (
        "python3 tests/regression/check_vpd_ramp_ui_independence.py",
        "python3 tests/regression/check_vpd_ramp_control.py",
        "python3 tests/regression/check_vpd_intelligent_control.py",
        "python3 tests/regression/check_profile_draft_management.py",
        "python3 tests/regression/check_settings_numeric_compatibility.py",
        "python3 tests/regression/check_light_sunrise_sunset.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
