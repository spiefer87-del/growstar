"""Growstar 3.17.20 / PROFILE.ACTIVATION-GUARD-UI.1 release metadata."""

RELEASE = {
    "version": "3.17.20",
    "date": "2026-09-14",
    "phase": "PROFILE.ACTIVATION-GUARD-UI.1",
    "title": "Sichtbarer Profil-Sperrgrund",
    "summary": (
        "Profile mit aktivem Sonnenverlauf erklären eine fehlende "
        "Licht-Controller-Zuordnung direkt an der Aktivierung."
    ),
    "changes": [
        "Ein fehlender Licht-Controller deaktiviert den Aktivierungsbutton nicht mehr kommentarlos.",
        "Beim Antippen erscheint der vollständige stationsbezogene Sperrgrund direkt unter dem Button.",
        "Bereits beim Auswählen eines betroffenen Profils wird der Sonnenverlauf als Ursache genannt.",
        "Ein direkter Link öffnet die Controller-Zuordnung für Beleuchtung und andere Geräte.",
        "Die serverseitige Sicherheitsprüfung bleibt erhalten und verhindert weiterhin einen nicht ausführbaren Sonnenverlauf.",
        "Profile ohne aktivierten Sonnenverlauf lassen sich unverändert sofort aktivieren.",
    ],
    "tests": [
        "python3 tests/regression/check_profile_activation_ui.py",
        "python3 tests/regression/check_light_sun_controller_guard.py",
        "python3 tests/regression/check_light_sun_controller_guard_2.py",
        "python3 tests/regression/check_profile_draft_management.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
