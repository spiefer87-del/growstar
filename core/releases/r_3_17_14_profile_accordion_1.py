"""Growstar 3.17.14 / UI.PROFILE-ACCORDION.1 release metadata."""

RELEASE = {
    "version": "3.17.14",
    "date": "2026-09-13",
    "phase": "UI.PROFILE-ACCORDION.1",
    "title": "Aufgeräumte Profil- und Klimaeinstellungen",
    "summary": (
        "Profilverwaltung sowie Klima & Grenzwerte verwenden kompakte Reiter, "
        "Klappbereiche und kontextbezogene Hilfedialoge."
    ),
    "changes": [
        "Die Profilverwaltung trennt klassische Regelung und VPD-Regelung über zwei Reiter.",
        "Zeiten, Temperatur, Feuchte, VPD, Rampe und Sonnenverlauf sind zunächst geschlossen aufklappbar.",
        "Beim Öffnen eines Bereichs wird der zuvor geöffnete Bereich automatisch geschlossen.",
        "Lange Erklärtexte wurden aus der Hauptansicht entfernt und hinter Info-Schaltflächen gebündelt.",
        "Die Seite Klima & Grenzwerte nutzt denselben Klappmechanismus innerhalb ihrer vorhandenen Reiter.",
        "Der Speicherbereich auf Klima & Grenzwerte ist nicht länger dauerhaft am Bildschirm fixiert.",
        "Speicher-, Aktivierungs- und Validierungslogik bleiben unverändert erhalten.",
    ],
    "tests": [
        "python3 tests/regression/check_profile_settings_accordion.py",
        "python3 tests/regression/check_profile_draft_management.py",
        "python3 tests/regression/check_profile_current_copy.py",
        "python3 tests/regression/check_settings_numeric_compatibility.py",
        "python3 tests/regression/check_vpd_auto_ui_lock.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
