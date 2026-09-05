"""Growstar 3.16.16 / PLANT.TIMELINE.1 release metadata."""

RELEASE = {
    "version": "3.16.16",
    "date": "2026-09-05",
    "phase": "PLANT.TIMELINE.1",
    "title": "Klassischer VPD-Sollwert und Ernteprognose",
    "summary": (
        "Die klassische Klimaregelung zeigt nun den aus Temperatur- und "
        "Feuchte-Sollwert berechneten VPD-Sollwert. Das Pflanzenmanagement "
        "ergänzt Sorten-Blütetage um eine dynamische Ernteprognose in Timeline "
        "und Pflanzendetail."
    ),
    "changes": (
        "Die VPD-Kachel zeigt bei ausgeschalteter intelligenter Regelung nicht mehr nur 'berechnet', sondern den konkreten klassischen Soll-VPD in kPa.",
        "Der klassische Soll-VPD wird mit derselben zentralen Formel wie der Live-VPD aus dem aktiven Temperatur- und Feuchte-Sollwert berechnet.",
        "Fehlende oder ungültige Sollwerte werden sicher als nicht verfügbar behandelt und erzeugen weder NaN noch einen API-Fehler.",
        "Intelligente VPD-Modi behalten ihre bisherige Ziel-, Rampen- und Strategiebeschriftung unverändert.",
        "Sobald für eine Pflanze ein Blütebeginn dokumentiert ist und die Sorte einen Blüte-Planwert besitzt, berechnet Growstar automatisch das voraussichtliche Erntedatum.",
        "Die Pflanzen-Timeline reicht automatisch bis zum spätesten prognostizierten Erntetermin.",
        "Eine gestrichelte Blüteplanung und ein Erntemarker zeigen Ist-Verlauf und Zukunftsprognose getrennt.",
        "Jede Timeline-Zeile nennt das Erntedatum sowie Resttage oder eine mögliche Überschreitung direkt neben der Pflanze.",
        "Das Pflanzendetail zeigt Blüte-Planwert, Ernteprognose, aktuellen Blütetag und Restzeit.",
        "Ohne dokumentierten Blütebeginn wird bewusst kein scheinpräzises Datum geraten; die Oberfläche weist auf den noch fehlenden Startpunkt hin.",
        "Änderungen am Blüte-Planwert der Sorte fließen ohne zusätzliche Pflanzendatenbankfelder direkt in die nächste Prognose ein.",
    ),
    "tests": (
        "python3 tests/regression/check_classic_vpd_and_harvest_forecast.py",
        "python3 tests/regression/check_vpd_intelligent_control.py",
        "python3 tests/regression/check_vpd_ui_cleanup.py",
        "python3 tests/regression/check_dashboard_header_mode.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
