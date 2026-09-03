"""Growstar 3.16.0 / VPD.CONTROL.1 release metadata."""

RELEASE = {
    "version": "3.16.0",
    "date": "2026-09-02",
    "phase": "VPD.CONTROL.1",
    "title": "Intelligente VPD-Steuerung mit Wirkungsprüfung",
    "summary": (
        "Growstar koordiniert Abluft, Heizung, Be- und Entfeuchtung innerhalb "
        "eines sicheren Temperatur-/Feuchtefensters. Jede Stufe wird anhand "
        "der realen VPD-Entwicklung bewertet, bevor die Regelung eskaliert."
    ),
    "changes": (
        "Aus, Beobachten und Automatisch trennen Vorbereitung, Diagnose und Aktorübernahme.",
        "Automatisch übernimmt ausschließlich Geräte, die ausdrücklich im ENV-Modus stehen.",
        "Tag- und Nacht-VPD, Toleranz sowie Temperatur- und Feuchtefenster sind konfigurierbar.",
        "VPD-Ziele und Betriebsfenster gehören zu den vorbereitbaren Profilvorlagen.",
        "Ein optionales, getrenntes Außenklima kann pro Station zugewiesen werden.",
        "Die Abluft wird nur genutzt, wenn die Außenluft physikalisch sinnvoll helfen kann.",
        "Nach dem Wirkungsfenster entscheidet der gemessene VPD-Trend über die nächste Stufe.",
        "Ohne ausreichende Abluftwirkung wird der Temperatursollwert nur schrittweise angehoben.",
        "Der Entfeuchter folgt erst als letzte Stufe nach wirkungsloser Abluft und Temperaturkorrektur.",
        "Bei zu hohem VPD werden zuerst Heizung und Abluft reduziert, danach folgt Befeuchtung.",
        "Feuchte-Hartgrenzen und das VPD-Temperaturfenster besitzen Vorrang vor Komfortkorrekturen.",
        "Fehlende, veraltete, identische oder unplausible Sensorquellen erzwingen klassischen Fallback.",
        "Sensor-, Profil- und VPD-Konfigurationswechsel setzen die flüchtige Wirkungshistorie zurück.",
        "Dashboard, Klimaseite und Profilverwaltung zeigen Ziel, Stufe und Betriebsbereitschaft an.",
        "Bestehende Profile erhalten abgeleitete VPD-Werte, ohne profiles.json ungefragt zu ändern.",
    ),
    "tests": (
        "python3 tests/regression/check_vpd_intelligent_control.py",
        "python3 tests/regression/check_optional_ppfd_assignment.py",
        "python3 tests/regression/check_profile_draft_management.py",
        "python3 tests/regression/check_profile_current_copy.py",
        "python3 tests/regression/check_settings_numeric_compatibility.py",
        "python3 tests/regression/check_fan_env_standby.py",
        "python3 tests/regression/check_safety_supervisor_thread.py",
        "python3 tests/regression/check_dashboard_header_mode.py",
        "python3 tests/regression/check_dashboard_phase_design.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
