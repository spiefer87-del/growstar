"""Growstar 3.16.25 / WATCHDOG.SYSTEM.1 release metadata."""

RELEASE = {
    "version": "3.16.25",
    "date": "2026-09-05",
    "phase": "WATCHDOG.SYSTEM.1",
    "title": "Live-Systemdaten des Raspberry Pi im Watchdog",
    "summary": (
        "Eine neue read-only Watchdog-Unterseite zeigt CPU, Temperatur, "
        "Arbeitsspeicher, Swap, Datenträger, Systemlast und Laufzeit des "
        "Raspberry Pi unabhängig von Grow-Regelungen und Pflanzendaten."
    ),
    "changes": (
        "Der Watchdog-Kopf besitzt einen direkten Button zur neuen Seite Systemdaten.",
        "CPU-Auslastung wird aus aufeinanderfolgenden Linux-/proc-Zählern berechnet und alle drei Sekunden aktualisiert.",
        "CPU-Temperatur wird auf Raspberry Pi über Linux-Thermal- beziehungsweise hwmon-Schnittstellen gelesen.",
        "Arbeitsspeicher, verfügbarer Speicher und Swap werden aus /proc/meminfo angezeigt.",
        "Belegter, freier und gesamter Speicherplatz des Systemdatenträgers wird separat dargestellt.",
        "Systemlast für 1, 5 und 15 Minuten, CPU-Kerne, Hostname, Kernel, Architektur, Python-Version und Laufzeit ergänzen die Diagnose.",
        "Die neue API ist vollständig read-only, fehlertolerant und benötigt keine zusätzliche psutil-Abhängigkeit.",
        "Seite und API verwenden die bestehende hardware.view-Berechtigung des Watchdogs.",
    ),
    "tests": (
        "python3 tests/regression/check_system_metrics_page.py",
        "python3 tests/regression/check_current_stage_date_correction.py",
        "python3 tests/regression/check_plant_photo_management.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
