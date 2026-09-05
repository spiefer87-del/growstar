"""Growstar 3.16.14 / VPD.CONTROL.8 release metadata."""

RELEASE = {
    "version": "3.16.14",
    "date": "2026-09-04",
    "phase": "VPD.CONTROL.8",
    "title": "VPD-Klimaziele mit einstellbarer Range",
    "summary": (
        "Temperatur und Luftfeuchtigkeit der intelligenten VPD-Regelung "
        "werden jetzt als Zielwert plus frei einstellbare Plus/Minus-Range "
        "konfiguriert. AUTO strebt darin einen gemeinsamen VPD-kompatiblen "
        "Klimapunkt an, statt an einer bisherigen Min/Max-Grenze anzuhalten."
    ),
    "changes": (
        "Klima & Grenzwerte zeigt für Tag und Nacht Temperatur-Ziel, Temperatur-Range, Feuchte-Ziel und Feuchte-Range.",
        "Die Profilverwaltung verwendet dieselben übersichtlichen Zielwert-plus-Range-Felder.",
        "Vorhandene Min/Max-Konfigurationen werden verlustfrei dargestellt: Der Mittelpunkt wird zum Zielwert und die halbe Spanne zur Range.",
        "Beim Speichern werden Zielwert und Range wieder in die bestehenden Min/Max-Schlüssel übersetzt; Konfigurationen, Profile und ältere Browserstände bleiben kompatibel.",
        "Der Regelkern sucht auf der erreichbaren VPD-Zielkurve den Klimapunkt mit dem kleinsten normierten Abstand zu Temperatur- und Feuchte-Ziel.",
        "Die aus Zielwert ± Range abgeleiteten Grenzen bleiben harte Sicherheitsgrenzen und werden von keinem veröffentlichten Sollwert überschritten.",
        "Eine frühere Obergrenze wie 62 Prozent ist nicht länger automatisch der Feuchtesollwert; AUTO führt innerhalb des VPD-Bands zum gekoppelten Zielpunkt weiter.",
        "Außerhalb des VPD-Bands bleibt die korrekte VPD-Richtung führend, damit kein Feuchteaktor den aktuellen VPD-Fehler verschärft.",
        "Bei zu hohem VPD und zugleich überhöhtem Feuchtewert wird nicht zusätzlich befeuchtet; zunächst wird der sichere Temperaturweg geprüft.",
        "Bei zu niedrigem VPD und bereits zu trockener Luft werden Abluft und Entfeuchter gesperrt; der Temperaturweg bleibt die passende Option.",
        "Der Live-State veröffentlicht bevorzugte Temperatur und Feuchte sowie Zielmittelpunkt und Range für Dashboard und Regellog.",
        "Der VPD-Regellog zeigt die Klimaziele als Zielwert ± Range und unterscheidet den bevorzugten Zielpunkt vom Rechenwert der aktuellen Temperaturstufe.",
    ),
    "tests": (
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
