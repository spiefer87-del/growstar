"""Growstar 3.15.11 / DASHBOARD.PROFILE.1 release metadata."""

RELEASE = {
    "version": "3.15.11",
    "date": "2026-09-01",
    "phase": "DASHBOARD.PROFILE.1",
    "title": "Klimamodus und Wachstumsphase klar visualisiert",
    "summary": (
        "Die Dashboard-Profilkarte priorisiert wieder Tag oder Nacht und zeigt "
        "darunter die aktive Wachstumsphase. Dezente phasenabhängige Farben "
        "verbinden alle Kacheln, ohne Gerätezustände zu überdecken."
    ),
    "changes": (
        "Profilwahlschalter folgen fest Vegetation, Blüte und Trocknung.",
        "Die Reihenfolge bleibt auch bei alphabetisch gelieferten API-Schlüsseln stabil.",
        "Zusätzliche zukünftige Profile erscheinen deterministisch hinter den drei Standardprofilen.",
        "Die Dashboard-Profilkarte heißt Klimamodus und zeigt Tag oder Nacht als Hauptinformation.",
        "Vegetation, Blüte oder Trocknung steht als separate Phasenmarke darunter.",
        "Tag verwendet einen warmen Sonnenverlauf, Nacht einen blau-violetten Verlauf.",
        "Vegetation verwendet Grün, Blüte Lila und Trocknung Dunkelorange beziehungsweise Amber.",
        "Alle Dashboard-Kacheln erhalten einen dünnen Phasenrand und einen sehr dezenten Schimmer.",
        "Die Klimamodus-Karte erhält einen etwas stärker sichtbaren, aber zurückhaltenden Verlauf.",
        "Gerätefarben für EIN, AUS, deaktiviert, Shadow und Safety behalten ihre bisherige Bedeutung.",
        "Die Karte führt weiterhin zuerst zu Klima & Grenzwerte.",
        "Die Darstellung bleibt dreispaltig und mobil optimiert.",
        "Reduzierte Bewegungen des Betriebssystems deaktivieren die Hover-Animation.",
        "Historische Dashboard-Regressionen prüfen die aktuellen Controller- und Linksignaturen.",
    ),
    "tests": (
        "python3 tests/regression/check_dashboard_phase_design.py",
        "python3 tests/regression/check_profile_draft_management.py",
        "python3 tests/regression/check_profile_current_copy.py",
        "python3 tests/regression/check_dashboard_controller_readback.py",
        "python3 tests/regression/check_dashboard_oscillation_active_state.py",
        "python3 tests/regression/check_dashboard_ppfd_card.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
