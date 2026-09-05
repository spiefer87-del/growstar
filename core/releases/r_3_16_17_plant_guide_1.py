"""Growstar 3.16.17 / PLANT.GUIDE.1 release metadata."""

RELEASE = {
    "version": "3.16.17",
    "date": "2026-09-05",
    "phase": "PLANT.GUIDE.1",
    "title": "VPD-Anbauhilfe nach Pflanzenphase",
    "summary": (
        "Das Pflanzenmanagement erhält einen schreibgeschützten VPD-Leitfaden "
        "für Tag und Nacht. Aktive Pflanzen werden anhand ihrer Phase und ihrer "
        "individuellen Sorten-Blütezeit automatisch eingeordnet; ein Live-Vergleich "
        "stellt die Messwerte einer Grow-Control-Station dem Empfehlungsband gegenüber."
    ),
    "changes": (
        "Die neue Seite 'Anbauhilfe' ist über Pflanzen-Navigation, Hauptmenü und Dashboard erreichbar.",
        "Sieben Stufen bilden Keimung, Sämling, frühe und späte Vegetation sowie frühe, mittlere und späte Blüte ab.",
        "Jede Stufe zeigt getrennte Tag- und Nachtziele mit VPD-Band und einem gekoppelten Beispiel aus Temperatur und Luftfeuchte.",
        "Aktive Pflanzen werden automatisch der passenden Tabellenzeile zugeordnet und dort namentlich markiert.",
        "Frühe, mittlere und späte Blüte richten sich nach 0–35 %, 35–75 % und 75–100 % der hinterlegten Sorten-Blütezeit.",
        "Ohne individuellen Planwert bleibt eine nachvollziehbare Fallback-Einteilung anhand der bisherigen Phasentage verfügbar.",
        "Der Live-Vergleich lädt vorhandene Grow-Control-Stationen und bewertet den aktuellen VPD gegen das Tag- oder Nachtband.",
        "Messwerte werden alle 15 Sekunden aktualisiert; Auswahl und Vergleich verändern keine Profile, Zielwerte oder Gerätezustände.",
        "Ein Fachhinweis trennt Luft-VPD ausdrücklich von Blatt-VPD und vermeidet pauschale Feuchteempfehlungen unter 40 Prozent.",
        "Die neue Darstellung ist für schmale Smartphone-Ansichten optimiert und hält die vollständige Tabelle horizontal erreichbar.",
    ),
    "tests": (
        "python3 tests/regression/check_vpd_cultivation_guide.py",
        "python3 tests/regression/check_classic_vpd_and_harvest_forecast.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
