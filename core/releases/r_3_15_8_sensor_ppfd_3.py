"""Growstar 3.15.8 / SENSOR.PPFD.3 release metadata."""

RELEASE = {
    "version": "3.15.8",
    "date": "2026-08-31",
    "phase": "SENSOR.PPFD.3",
    "title": "Helligkeitssensor bei Zelt-Zuweisungen optional",
    "summary": (
        "Temperatur- und Feuchtesensoren lassen sich wieder unabhängig "
        "zuweisen, auch wenn ein Zelt keinen Helligkeits- oder PPFD-Sensor besitzt."
    ),
    "changes": (
        "Eine leere PPFD-Auswahl ist bei stationsbezogenen Sensorzuweisungen zulässig.",
        "Leere PPFD-Daten entfernen ausschließlich eine eventuell alte PPFD-Zuweisung.",
        "Temperatur- und Feuchtezuweisungen werden im selben Speichervorgang weiterhin übernommen.",
        "Teilupdates ohne PPFD-Feld behalten eine bereits gespeicherte PPFD-Zuweisung.",
        "Gültige PPFD-Zuweisungen sowie Temperatur und Feuchte bleiben streng validiert.",
        "Sensorlaufzeit, Messwertpfad, Offsets und Regelung bleiben unverändert.",
    ),
    "tests": (
        "python3 tests/regression/check_optional_ppfd_assignment.py",
        "python3 tests/regression/check_sensor_ppfd_assignment_hardware.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
