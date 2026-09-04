"""Growstar 3.16.7 / VPD.UI.2 release metadata."""

RELEASE = {
    "version": "3.16.7",
    "date": "2026-09-04",
    "phase": "VPD.UI.2",
    "title": "Sichtbare VPD-Aktorübernahme und Live-Regelplan",
    "summary": (
        "Von VPD-AUTO übernommene Aktoren sind auf dem Dashboard und in ihren "
        "Details eindeutig gekennzeichnet, gegen manuelle Änderungen geschützt "
        "und durch einen echten Live-Regelplan nachvollziehbar."
    ),
    "changes": (
        "Heizung, Abluft, Befeuchter und Entfeuchter zeigen bei AUTO/ENV den Modus VPD intelligent.",
        "Ein kompaktes Badge unterscheidet aktive Übernahme und sicheren Sensor-Fallback.",
        "Die Gerätekachel zeigt Strategie und aktuell angeforderten EIN/AUS- beziehungsweise Leistungszustand.",
        "Nicht vom VPD-Regler verwaltete Geräte wie Licht, Umluft und Bewässerung bleiben normal bedienbar.",
        "Die Gerätedetailseite sperrt alle Modus-, Zeit-, Intervall-, ENV- und Controllerregler während der AUTO-Übernahme.",
        "Der Schreibschutz wird mit HTTP 423 zusätzlich serverseitig erzwungen und gilt auch für alte Browser-Tabs.",
        "AUTO/ENV bleibt während eines Sensor-Fallbacks gesperrt, damit die Regelung später ohne Konfigurationssprung fortsetzen kann.",
        "Ein direkter Link führt aus der Sperrmeldung zu Klima & Grenzwerte, wo AUTO verlassen werden kann.",
        "Die neue Live-Infokarte zeigt Zielband, Klimafenster, Außenluftbewertung und Wirkungs-Countdown.",
        "Der Aktorplan nennt alle beteiligten Geräte samt Sollzustand und gegebenenfalls Controllerstufe.",
        "Die Zustandsmaschine veröffentlicht einen ehrlichen bedingten nächsten Prüfschritt statt einer statischen Statusmeldung.",
        "Beobachten zeigt denselben simulierten Live-Regelplan, sperrt die Gerätekonfiguration aber nicht.",
        "Es gibt keine Konfigurationsmigration und keine Veränderung bestehender VPD-Regelwerte.",
    ),
    "tests": (
        "python3 tests/regression/check_vpd_auto_ui_lock.py",
        "python3 tests/regression/check_vpd_intelligent_control.py",
        "python3 tests/regression/check_vpd_ramp_control.py",
        "python3 tests/regression/check_vpd_ramp_ui_independence.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
