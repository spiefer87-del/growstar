"""Growstar 3.16.8 / VPD.CONTROL.3 release metadata."""

RELEASE = {
    "version": "3.16.8",
    "date": "2026-09-04",
    "phase": "VPD.CONTROL.3",
    "title": "Vollständige Abluft- und Temperatur-Eskalation",
    "summary": (
        "Bei zu niedrigem VPD durchläuft Growstar jetzt jede sichere "
        "Abluftstufe und anschließend jede erreichbare Temperaturstufe, statt "
        "den Regelweg nach einer einzelnen schwachen Messung abzubrechen."
    ),
    "changes": (
        "Jede Abluftstufe erhält ein vollständiges, konfiguriertes Wirkungsfenster.",
        "Eine schwache Einzelmessung beendet den Abluftweg nicht mehr vorzeitig.",
        "Eine zugewiesene Spider-Farmer-Abluft darf über die normale ENV-Leistung bis zur sicheren Blower-Obergrenze von 100 Prozent steigen.",
        "Der Abluft-Schritt wird eindeutig als Prozentpunkte interpretiert, zum Beispiel 75 auf 85 bei Schrittweite 10.",
        "Ohne bestätigte Controllerzuordnung bleibt die bisherige ENV-Regelleistung weiterhin die konservative Obergrenze.",
        "Das Abluft-Maximum wird selbst noch ein vollständiges Intervall lang geprüft, bevor die Temperatur übernimmt.",
        "Nach der Abluft erhöht Growstar den Temperatur-Sollwert schrittweise bis zum aktiven Tag-/Nacht-Maximum.",
        "Eine bereits erreichte Temperaturstufe gibt den nächsten Schritt auch dann frei, wenn die einzelne VPD-Wirkung noch klein ist.",
        "Eine noch nicht erreichte Temperaturstufe wird gehalten, solange die Heizung messbar reagiert.",
        "Erst zwei vollständige Intervalle ohne Temperaturreaktion markieren den Heizpfad als technisch unwirksam.",
        "Der Entfeuchter wird erst nach ausgeschöpftem beziehungsweise nachweislich unwirksamem Abluft- und Temperaturweg angefordert.",
        "Der Zustand Keine weitere Aktorstufe wird nun periodisch neu bewertet und ist kein eingefrorenes Ende mehr.",
        "Alle Temperatur-, Feuchte- und Controllergrenzen bleiben verbindlich; es gibt keine unbeschränkte Eskalation.",
        "Die Live-Infokarte zeigt Abluftstufe, Controllermaximum, Temperaturziel und Temperaturmaximum als Stufenfortschritt.",
        "Die Wirkungsanzeige behält das Ergebnis des letzten abgeschlossenen Prüfintervalls sichtbar.",
        "Nächster Schritt nennt konkrete Folgewerte für Abluft und Temperatur.",
        "Die Einstellungsseite erklärt den vollständigen Stufenweg und die neue Bedeutung der Mindestwirkung.",
        "Es gibt keine Konfigurationsmigration; vorhandene Ziel-, Schritt- und Zeitwerte bleiben erhalten.",
    ),
    "tests": (
        "python3 tests/regression/check_vpd_progressive_escalation.py",
        "python3 tests/regression/check_vpd_intelligent_control.py",
        "python3 tests/regression/check_vpd_auto_ui_lock.py",
        "python3 tests/regression/check_vpd_ramp_control.py",
        "python3 tests/regression/check_vpd_ramp_ui_independence.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
