"""Growstar 3.16.3 / SENSOR.OUTSIDE.2 release metadata."""

RELEASE = {
    "version": "3.16.3",
    "date": "2026-09-03",
    "phase": "SENSOR.OUTSIDE.2",
    "title": "Getrennte Kalibrierung der Außensensoren",
    "summary": (
        "Außen-Temperatur und Außen-Luftfeuchte besitzen nun eigene, "
        "stationsbezogene Offsets. RAW- und korrigierte Werte bleiben sichtbar, "
        "während die VPD-Steuerung ausschließlich mit den korrigierten Werten arbeitet."
    ),
    "changes": (
        "Die Sensordetailseite bietet Plus/Minus- und Direkteingaben für beide Außen-Offsets.",
        "Außen-Temperatur und Außen-Luftfeuchte werden unabhängig voneinander kalibriert.",
        "RAW- und korrigierte Außenwerte werden gleichzeitig angezeigt.",
        "Die VPD-Steuerung verwendet ausschließlich die korrigierten Außenmesswerte.",
        "Innen- und Außen-Offsets bleiben vollständig voneinander getrennt.",
        "Beide Außen-Offsets werden ausschließlich in der jeweiligen Stationskonfiguration gespeichert.",
        "Bestehende Stationen erhalten rückwärtskompatibel den sicheren Standardwert 0.0.",
        "Nicht-endliche Offsetwerte wie NaN oder Unendlich werden serverseitig abgewiesen.",
        "Eine geänderte Außenkalibrierung startet die VPD-Wirkungsprüfung mit frischen Messwerten neu.",
        "Beim Entfernen einer Außenquelle werden RAW- und korrigierter Wert gemeinsam geleert.",
        "Der gemeinsame Speicherknopf wartet auf noch ausstehende Offset-Speicherungen.",
    ),
    "tests": (
        "python3 tests/regression/check_optional_ppfd_assignment.py",
        "python3 tests/regression/check_vpd_intelligent_control.py",
        "python3 tests/regression/check_settings_numeric_compatibility.py",
        "python3 tests/regression/check_safety_supervisor_thread.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
