"""Growstar 3.16.11 / VPD.CONTROL.5 release metadata."""

RELEASE = {
    "version": "3.16.11",
    "date": "2026-09-04",
    "phase": "VPD.CONTROL.5",
    "title": "Temperaturreserve nach ausgeschöpfter Abluft",
    "summary": (
        "VPD-AUTO nutzt nach einer vollständig geprüften Maximalabluft die "
        "gesamte konfigurierte Temperaturreserve, statt den Heizweg wegen "
        "des bevorzugten Feuchtefensters vorzeitig zu sperren."
    ),
    "changes": (
        "Der in 3.16.10 eingeführte falsche Temperaturdeckel aus der rechnerischen Schnittmenge von VPD-Ziel und Feuchtefenster wurde entfernt.",
        "Bei zu niedrigem VPD wechselt die Strategie nach vollständig geprüfter Abluft 100 korrekt auf Temperatur anheben.",
        "Der Heizweg darf in geprüften VPD_TEMP_STEP-Schritten bis zur konfigurierten VPD-Temperatur-Obergrenze laufen.",
        "Die maximale Abluftstufe bleibt während des anschließenden Heizwegs aktiv, solange trockenere Außenluft verfügbar ist.",
        "Sobald der gemessene VPD das Zielband erreicht, wird ein noch höherer Temperatursollwert sofort verworfen und die Heizung beendet.",
        "Das Feuchtefenster bleibt der bevorzugte Arbeitsbereich für Abluft, Be- und Entfeuchtung, erzwingt aber keine dem VPD widersprechende Regelrichtung.",
        "Der mathematische Feuchtesollwert wird weiterhin live für jede Temperaturstufe berechnet und darf als Rechenwert außerhalb des bevorzugten Feuchtefensters liegen.",
        "Bei 1,10 kPa werden für 23,9 Grad rund 62,9 Prozent, für 24,4 Grad rund 64,0 Prozent und für 26 Grad rund 67,3 Prozent ausgewiesen.",
        "Die klassische Temperatur-Regeltoleranz kann einen VPD-Heizschritt nicht mehr verhindern; AUTO nutzt eine kleine eigene Hysterese.",
        "Die klassische Luftfeuchtigkeitsregelung und ihre Toleranz bleiben von einem bereiten VPD-AUTO-Plan getrennt.",
        "Einstellungsseite, Profilverwaltung und Regellog erklären die Rollen von Temperaturgrenzen und Feuchte-Arbeitsfenster eindeutig.",
        "Stationsweite MIN_TEMP/MAX_TEMP- und Safety-Grenzen, Sensor-Fallback sowie die ENV-Aktorautorität bleiben unverändert aktiv.",
        "Es gibt keine Konfigurationsmigration und keine Änderung gespeicherter Profile, Sensorzuweisungen oder Gerätesollwerte.",
    ),
    "tests": (
        "python3 tests/regression/check_vpd_heating_after_exhaust.py",
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
