"""Growstar 3.16.4 / VPD.RAMP.1 release metadata."""

RELEASE = {
    "version": "3.16.4",
    "date": "2026-09-03",
    "phase": "VPD.RAMP.1",
    "title": "Phasenweiche VPD-Rampe mit bevorzugter Temperaturabsenkung",
    "summary": (
        "Im intelligenten Modus führt die Profilrampe nun VPD-Ziel, Toleranz "
        "und erlaubte Klima-Fenster gleitend von Tag zu Nacht und zurück. "
        "Bei zu hohem VPD wird zuerst die Temperatur innerhalb Min/Max gesenkt."
    ),
    "changes": (
        "Die Abendrampe interpoliert VPD_TARGET_DAY bis VPD_TARGET_NIGHT.",
        "Die Morgenrampe interpoliert spiegelbildlich vom Nacht- zum Tagesziel.",
        "VPD-Toleranz sowie Temperatur- und Feuchtefenster wechseln gleichzeitig gleitend.",
        "AUTO verwendet keine klassische DAY_TEMP/NIGHT_TEMP-Rampe mehr als VPD-Regelbasis.",
        "DAY_TEMP und NIGHT_TEMP bleiben bei fehlender VPD-Bereitschaft als sicherer klassischer Fallback erhalten.",
        "MONITOR berechnet dieselbe VPD-Rampe, verändert aber weder Sollwert noch Aktoren.",
        "Bei zu hohem VPD wird das Temperaturziel zuerst schrittweise bis zur erlaubten Untergrenze abgesenkt.",
        "Geeignete kühlere Außenluft kann die bevorzugte Temperaturabsenkung unterstützen.",
        "Erst nach ausbleibender Wirkung folgen Luftbefeuchter oder unterstützende feuchtere Außenluft.",
        "Das Dashboard zeigt Zielwert, Fortschritt und Richtung einer aktiven VPD-Rampe.",
        "Vollständige Browser-Payloads lösen nur noch für tatsächlich veränderte Werte Seiteneffekte aus.",
        "Ein reines VPD-Speichern kann eine laufende Temperatur-Rampe nicht mehr neu starten.",
        "Echte Änderungen einer Abendrampe behalten Nachtziel und Endzeit statt auf das Tagesziel umzudrehen.",
    ),
    "tests": (
        "python3 tests/regression/check_vpd_ramp_control.py",
        "python3 tests/regression/check_vpd_intelligent_control.py",
        "python3 tests/regression/check_morning_ramp_profile_sync.py",
        "python3 tests/regression/check_profile_draft_management.py",
        "python3 tests/regression/check_profile_current_copy.py",
        "python3 tests/regression/check_settings_numeric_compatibility.py",
        "python3 tests/regression/check_safety_supervisor_thread.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
