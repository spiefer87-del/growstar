"""Growstar 3.17.13 / INTELLIGENCE.DEVICES.1 release metadata."""

RELEASE = {
    "version": "3.17.13",
    "date": "2026-09-12",
    "phase": "INTELLIGENCE.DEVICES.1",
    "title": "Gerätewerte und Aktorwechsel in Grow Intelligence",
    "summary": (
        "Gespeicherte Geräte-Sollwerte und erfolgreiche Shelly-Schaltwechsel "
        "werden stationsbezogen und ohne Regelzyklus-Rauschen protokolliert."
    ),
    "changes": [
        "Lichtstärke, Ventilatorstufe und Oszillation zeigen konkrete Vorher-/Nachher-Werte.",
        "Dauer-, Zeit-, ENV-, Intervall- sowie Tag-/Nacht-Zustände werden eindeutig benannt.",
        "Modus, Zeitfenster, Intervalldauern, Shelly-Power und ENV-Optionen sind ebenfalls angebunden.",
        "Erfolgreiche EIN/AUS-Schaltbefehle erscheinen mit Gerät, Station, Modus und vorhandenem Regelgrund.",
        "Unveränderte Regelzyklen, blockierte Befehle und fehlgeschlagene Hardwarezugriffe erzeugen keine Timeline-Flut.",
        "Konfiguration und Timeline bleiben technisch entkoppelt; ein Ereignisfehler blockiert keinen Aktor.",
    ],
    "tests": [
        "python3 tests/regression/check_grow_intelligence_device_events.py",
        "python3 tests/regression/check_grow_intelligence_setting_changes.py",
        "python3 tests/regression/check_grow_intelligence_integration.py",
        "python3 tests/regression/check_controller_power_gate.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
