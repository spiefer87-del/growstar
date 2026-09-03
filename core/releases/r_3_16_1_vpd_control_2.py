"""Growstar 3.16.1 / VPD.CONTROL.2 release metadata."""

RELEASE = {
    "version": "3.16.1",
    "date": "2026-09-03",
    "phase": "VPD.CONTROL.2",
    "title": "Getrennte VPD-Klimafenster für Tag und Nacht",
    "summary": (
        "VPD-Ziel, Toleranz sowie Temperatur- und Feuchtefenster lassen sich "
        "für Tag und Nacht vollständig getrennt vorbereiten. Beim Phasenwechsel "
        "beginnt die Wirkungsprüfung sicher mit den neu aktiven Grenzen."
    ),
    "changes": (
        "Tag und Nacht besitzen jeweils eine eigene VPD-Toleranz.",
        "Temperatur-Minimum und -Maximum sind für beide Phasen getrennt konfigurierbar.",
        "Feuchte-Minimum und -Maximum sind für beide Phasen getrennt konfigurierbar.",
        "Klimaseite und Profilverwaltung zeigen zwei klar getrennte Tag-/Nacht-Bereiche.",
        "Die Vorschau prüft die physikalische Erreichbarkeit für jede Phase einzeln.",
        "Der Regler wählt Zielband und Betriebsfenster anhand der aktuell aktiven Phase.",
        "Ein Tag-/Nachtwechsel verwirft die alte Wirkungshistorie und startet die Stufe neu.",
        "Stations-Schutzgrenzen werden für Tag und Nacht unabhängig validiert.",
        "Bestehende gemeinsame 3.16.0-Werte werden ohne Datenverlust auf beide Phasen gespiegelt.",
        "Bereits gespeicherte Profile werden nur im Arbeitsspeicher migriert und nicht ungefragt geschrieben.",
        "Noch geöffnete 3.16.0-Browserseiten können ihre gemeinsamen Felder weiterhin sicher speichern.",
        "Der Betriebsmodus Aus, Beobachten oder Automatisch bleibt weiterhin stationsbezogen.",
    ),
    "tests": (
        "python3 tests/regression/check_vpd_intelligent_control.py",
        "python3 tests/regression/check_profile_draft_management.py",
        "python3 tests/regression/check_profile_current_copy.py",
        "python3 tests/regression/check_settings_numeric_compatibility.py",
        "python3 tests/regression/check_morning_ramp_profile_sync.py",
        "python3 tests/regression/check_optional_ppfd_assignment.py",
        "python3 tests/regression/check_fan_env_standby.py",
        "python3 tests/regression/check_safety_supervisor_thread.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
