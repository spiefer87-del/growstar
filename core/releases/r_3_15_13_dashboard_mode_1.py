"""Growstar 3.15.13 / DASHBOARD.MODE.1 release metadata."""

RELEASE = {
    "version": "3.15.13",
    "date": "2026-09-01",
    "phase": "DASHBOARD.MODE.1",
    "title": "Tag und Nacht in den Stationskopf verschoben",
    "summary": (
        "Ein kompakter Sonnen- oder Mondindikator nutzt den freien Bereich im "
        "Stationskopf. Die Dashboard-Kachel konzentriert sich wieder vollständig "
        "auf das aktive Profil und den Einstieg zu Klima & Grenzwerte."
    ),
    "changes": (
        "Tag/Nacht wird als runder Symbolindikator links im Stationskopf dargestellt.",
        "Der Indikator nutzt auf Mobilgeräten den freien Raum unter den Zeltinformationen.",
        "Tag behält den warmen Gelb-/Orangeverlauf und das Sonnensymbol.",
        "Nacht behält den kontrastreichen Blau-/Violettverlauf und das Mondsymbol.",
        "TAG beziehungsweise NACHT ist vollständig aus der Profilkachel entfernt.",
        "Die Kachel trägt wieder die eindeutige Überschrift Profil.",
        "Vegetation, Blüte oder Trocknung ist die Hauptinformation der Profilkachel.",
        "Klima & Grenzwerte bleibt das unveränderte Linkziel.",
        "Phasenränder, Gerätezustandsfarben und mobile Dreispaltenansicht bleiben erhalten.",
        "Der reine Symbolindikator besitzt einen zugänglichen Tag-/Nacht-Text für Screenreader.",
    ),
    "tests": (
        "python3 tests/regression/check_dashboard_header_mode.py",
        "python3 tests/regression/check_dashboard_phase_design.py",
        "python3 tests/regression/check_profile_draft_management.py",
        "python3 tests/regression/check_profile_current_copy.py",
        "python3 tests/regression/check_dashboard_controller_readback.py",
        "python3 tests/regression/check_dashboard_ppfd_card.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
