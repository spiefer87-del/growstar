"""Growstar 3.16.10 / VPD.CONTROL.4 release metadata."""

RELEASE = {
    "version": "3.16.10",
    "date": "2026-09-04",
    "phase": "VPD.CONTROL.4",
    "title": "Stabile Maximalabluft und gekoppelte VPD-Sollwerte",
    "summary": (
        "VPD-AUTO hält eine vollständig eskalierte Abluft bei weiterhin "
        "geeigneter Außenluft auf ihrer erreichten Maximalstufe und berechnet "
        "Temperatur- und Feuchtesollwert erstmals als gemeinsames, innerhalb "
        "der konfigurierten Grenzen erreichbares VPD-Zielpaar."
    ),
    "changes": (
        "Die Stufe Keine weitere Aktorstufe fällt nicht mehr fälschlich von 100 Prozent auf die 75-Prozent-Grundlüftung zurück.",
        "Eine ausgeschöpfte Abluft bleibt auf ihrer letzten VPD-Stufe, solange Entfeuchtungsbedarf und geeignete trockenere Außenluft fortbestehen.",
        "Standby beziehungsweise Grundlüftung übernimmt erst wieder im VPD-Zielzustand oder wenn die Außenluft nicht mehr zum Trocknen geeignet ist.",
        "Die klassische Feuchteregeltoleranz bestimmt weiterhin keine Entscheidung eines bereiten VPD-AUTO-Plans.",
        "VPD-AUTO berechnet aus seinem VPD-Ziel und dem wirksamen Temperaturziel fortlaufend den passenden Feuchtesollwert.",
        "Temperatur- und Feuchtefenster werden als gekoppelte harte Grenzen ausgewertet und nicht mehr als widersprüchliche Einzelziele behandelt.",
        "Ist die konfigurierte Maximaltemperatur mit dem Feuchtefenster nicht vereinbar, wird das VPD-Temperaturziel auf den erreichbaren Kurvenabschnitt begrenzt.",
        "Für 1,10 kPa bei 26,0 Grad wird beispielsweise der rechnerische Bedarf von rund 67,3 Prozent Luftfeuchtigkeit ausgewiesen.",
        "Bei einem Feuchtemaximum von 60 Prozent wird für dasselbe VPD-Ziel stattdessen ein erreichbares Zielpaar von rund 22,65 Grad und 60 Prozent verwendet.",
        "Das Dashboard zeigt in VPD-AUTO die gemeinsam berechneten Live-Sollwerte statt des alten klassischen Feuchtesollwerts.",
        "Im Beobachten-Modus bleiben die klassischen Live-Sollwerte unverändert; das gekoppelte Zielpaar wird nur simuliert und im Regellog angezeigt.",
        "Fallback, Ausschalten und VPD-Reset stellen die getrennt gesicherten klassischen Temperatur- und Feuchtesollwerte sofort wieder her.",
        "Der VPD-Regellog zeigt Zielpaar, dynamisches Feuchte-Zielband, den erreichbaren Temperaturabschnitt und eine verständliche Grenzerklärung.",
        "Der Stufenweg unterscheidet zwischen dem aktuell erreichbaren VPD-Temperaturmaximum und der allgemein konfigurierten Temperaturobergrenze.",
        "Es gibt keine Konfigurationsmigration und keine Änderung gespeicherter Profile oder Gerätesollwerte.",
    ),
    "tests": (
        "python3 tests/regression/check_vpd_coupled_targets.py",
        "python3 tests/regression/check_vpd_progressive_escalation.py",
        "python3 tests/regression/check_vpd_intelligent_control.py",
        "python3 tests/regression/check_vpd_ramp_control.py",
        "python3 tests/regression/check_vpd_ramp_ui_independence.py",
        "python3 tests/regression/check_vpd_auto_ui_lock.py",
        "python3 tests/regression/check_vpd_ui_cleanup.py",
        "python3 tests/regression/check_settings_numeric_compatibility.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
