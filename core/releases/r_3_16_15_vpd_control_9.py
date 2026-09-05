"""Growstar 3.16.15 / VPD.CONTROL.9 release metadata."""

RELEASE = {
    "version": "3.16.15",
    "date": "2026-09-05",
    "phase": "VPD.CONTROL.9",
    "title": "Wählbare zweite VPD-Priorität",
    "summary": (
        "VPD bleibt immer das führende Regelziel. Für Tag und Nacht kann nun "
        "separat gewählt werden, ob Feuchtigkeit oder Temperatur als zweite "
        "Priorität auf der VPD-Zielkurve behandelt wird. Bei Feuchte-Priorität "
        "prüft Growstar während einer Heizstufe zugleich die Feuchtewirkung und "
        "schaltet einen verfügbaren Entfeuchter bei ausbleibender Abnahme früher zu."
    ),
    "changes": (
        "Klima & Grenzwerte bietet für Tag und Nacht die Auswahl Priorität 2: Feuchtigkeit oder Temperatur.",
        "Profilvorlagen speichern und aktivieren dieselbe phasenbezogene Prioritätsauswahl.",
        "Vorhandene Konfigurationen und Profile erhalten rückwärtskompatibel Feuchtigkeit als zweite Priorität.",
        "VPD ist unveränderlich Priorität 1; harte Temperatur- und Feuchte-Ranges bleiben darüber hinaus verbindliche Sicherheitsgrenzen.",
        "Bei Feuchte-Priorität wird der Feuchte-Zielwert exakt auf der erreichbaren VPD-Zielkurve angestrebt; Temperatur ist dann nachrangig.",
        "Bei Temperatur-Priorität wird entsprechend der Temperatur-Zielwert exakt angestrebt; Feuchtigkeit bleibt nachrangig innerhalb ihrer Range.",
        "Innerhalb des VPD-Zielbands wird ausschließlich die gewählte zweite Priorität nachgeführt, sodass die dritte Zielgröße keinen widersprüchlichen Aktorweg auslöst.",
        "Bei Temperatur-Priorität beginnt ein VPD-Anhebepfad mit verfügbarer Temperaturreserve bevorzugt mit der Heizung.",
        "Bei Feuchte-Priorität werden während jeder Heizprobe Temperaturanstieg und Feuchteabnahme parallel ausgewertet.",
        "Sinkt die relative Feuchte innerhalb des ersten Wirkungsfensters nicht um mindestens 0,3 Prozentpunkte oder steigt sie, übernimmt ein verfügbarer Entfeuchter sofort die nächste Stufe.",
        "Eine messbare Feuchteabnahme lässt die Heizprobe weiterlaufen; der Entfeuchter wird nicht unnötig zugeschaltet.",
        "Der VPD-Regellog zeigt Priorität 1 und 2, Feuchteabnahme sowie die Entscheidung zur frühen Entfeuchtung live an.",
        "Dashboard-Sollwerte bleiben an den gekoppelten VPD-Zielpunkt gebunden und überschreiten keine konfigurierte Range.",
    ),
    "tests": (
        "python3 tests/regression/check_vpd_secondary_priority.py",
        "python3 tests/regression/check_vpd_target_range_control.py",
        "python3 tests/regression/check_vpd_hard_humidity_limits.py",
        "python3 tests/regression/check_vpd_coupled_targets.py",
        "python3 tests/regression/check_vpd_heating_after_exhaust.py",
        "python3 tests/regression/check_vpd_adaptive_cadence.py",
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
