"""Growstar 3.16.9 / VPD.UI.3 release metadata."""

RELEASE = {
    "version": "3.16.9",
    "date": "2026-09-04",
    "phase": "VPD.UI.3",
    "title": "Kompaktes Dashboard und separater VPD-Regellog",
    "summary": (
        "Die ausführliche VPD-Diagnose verlässt das Dashboard und erhält eine "
        "eigene, live aktualisierte Regellog-Seite. Klima- und VPD-Regelwerte "
        "sind auf der Einstellungsseite jetzt klar getrennt."
    ),
    "changes": (
        "Die große VPD-Infokarte wurde vollständig aus der Dashboard-Kachelansicht entfernt.",
        "Die VPD-Kachel zeigt bei Beobachten oder Automatik einen kleinen Regellog-Zugang.",
        "Der normale Klick auf die VPD-Kachel öffnet weiterhin den Messwertverlauf.",
        "Eine neue stationsbezogene Live-Seite zeigt Strategie, Begründung, Zielband, Klimafenster, Außenluft, Wirkung, Stufenweg und Aktorplan.",
        "Der Live-Regellog aktualisiert sich alle zwei Sekunden über die bereits vorhandene Stations-State-API.",
        "Die letzten Regelentscheidungen werden mit Uhrzeit, VPD, Temperatur, Abluftstufe und Temperaturziel angezeigt.",
        "Der veröffentlichte Verlauf ist auf 20, der interne Verlauf auf 30 Einträge begrenzt.",
        "Interne Messsamples und Zustandsmaschinen-Caches bleiben weiterhin privat.",
        "Tag-/Nachtwechsel starten die Regelstrategie neu, behalten aber den kurzen Diagnoseverlauf bei.",
        "Die Seite Klima & Grenzwerte besitzt nun getrennte Ansichten für klassische und intelligente Regelung.",
        "Beim Öffnen wird automatisch die zur gespeicherten VPD-Betriebsart passende Ansicht gewählt.",
        "Das Umschalten der Ansicht verändert keine Werte und aktiviert keine Betriebsart.",
        "Der gemeinsame Speichern-/Verwerfen-Entwurf bleibt unverändert erhalten.",
        "Tag- und Nachtzeiten bleiben als gemeinsame Zeitbasis in beiden Ansichten sichtbar.",
        "Die eigenständige VPD-Rampe bleibt unabhängig von Sonnenaufgang, Sonnenuntergang und Helligkeitssensor konfigurierbar.",
        "Bei aktivem VPD-Automatikmodus bleiben klassische Sollwerte beim manuellen Wechsel zur klassischen Ansicht sichtbar, aber gesperrt.",
        "Ein kompakter Live-Regellog-Button erscheint auch auf der Klimaseite, sobald Beobachten oder Automatik gewählt ist.",
        "Gerätekacheln, VPD-AUTO-Badges und die bestehenden Schreibsperren der übernommenen ENV-Aktoren bleiben unverändert.",
        "Der Patch verändert keine VPD-Regelstrategie und keine gespeicherten Konfigurationswerte.",
    ),
    "tests": (
        "python3 tests/regression/check_vpd_ui_cleanup.py",
        "python3 tests/regression/check_vpd_auto_ui_lock.py",
        "python3 tests/regression/check_vpd_progressive_escalation.py",
        "python3 tests/regression/check_vpd_intelligent_control.py",
        "python3 tests/regression/check_vpd_ramp_control.py",
        "python3 tests/regression/check_vpd_ramp_ui_independence.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
