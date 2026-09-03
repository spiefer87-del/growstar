"""Growstar 3.16.2 / SENSOR.OUTSIDE.1 release metadata."""

RELEASE = {
    "version": "3.16.2",
    "date": "2026-09-03",
    "phase": "SENSOR.OUTSIDE.1",
    "title": "Außensensoren manuell in den Sensordetails zuweisen",
    "summary": (
        "Außen-Temperatur und Außen-Luftfeuchte lassen sich nun direkt auf "
        "der stationsbezogenen Seite Offsets & Details auswählen, ändern und "
        "einzeln entfernen. Drag & Drop bleibt als zusätzliche Übersicht erhalten."
    ),
    "changes": (
        "Die Sensordetailseite besitzt eigene Dropdowns für Außen-Temperatur und Außen-Luftfeuchte.",
        "Beide Außenzuweisungen werden gemeinsam mit Innenwerten und PPFD über den vorhandenen Speicherknopf bestätigt.",
        "Außensensoren bleiben optional und können unabhängig voneinander auf nicht zugewiesen gesetzt werden.",
        "Aktuell angewendete Außenmesswerte und die jeweils gespeicherte Quelle werden direkt angezeigt.",
        "Vorübergehend nicht verfügbare, aber gespeicherte Quellen bleiben auswählbar und werden nicht versehentlich überschrieben.",
        "Die Sensor-API liefert explizite Optionslisten für beide Außenmessfelder.",
        "Innen-Temperatur und Innen-Luftfeuchte bleiben weiterhin verpflichtende Regelungsquellen.",
        "Eine geänderte Außenquelle setzt die laufende VPD-Wirkungsprüfung sicher zurück.",
        "Die bestehende Drag-&-Drop-Sensorverwaltung bleibt unverändert nutzbar.",
    ),
    "tests": (
        "python3 tests/regression/check_optional_ppfd_assignment.py",
        "python3 tests/regression/check_sensor_ppfd_assignment_hardware.py",
        "python3 tests/regression/check_vpd_intelligent_control.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_release_system.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
