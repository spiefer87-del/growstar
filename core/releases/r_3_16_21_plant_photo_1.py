"""Growstar 3.16.21 / PLANT.PHOTO.1 release metadata."""

RELEASE = {
    "version": "3.16.21",
    "date": "2026-09-05",
    "phase": "PLANT.PHOTO.1",
    "title": "Mobiler Foto-Manager für Pflanzen",
    "summary": (
        "Pflanzenfotos können direkt per Smartphone-Kamera aufgenommen, "
        "platzsparend gespeichert und automatisch mit Pflanze, Phase, "
        "Timeline und Betriebsjournal verbunden werden."
    ),
    "changes": (
        "Auf dem Pflanzenmanagement-Dashboard steht neben Sorte und Pflanze der neue Schnellzugriff '+ Fotos' bereit.",
        "Der mobile Aufnahmedialog öffnet über capture=environment bevorzugt die rückseitige Smartphone-Kamera.",
        "Jedes Foto wird einer aktiven Pflanze, einem Aufnahmezeitpunkt und einer optionalen Notiz zugeordnet.",
        "Die zum Aufnahmezeitpunkt gültige Lifecycle-Phase wird aus dem Phasenverlauf ermittelt und dauerhaft am Foto gespeichert.",
        "Bilder werden serverseitig gedreht, auf maximal 1600 Pixel Kantenlänge reduziert und als optimiertes JPEG mit Qualitätsstufe 82 gespeichert.",
        "EXIF-Metadaten einschließlich möglicher Standortdaten werden beim Neukodieren entfernt.",
        "Der Foto-Manager filtert nach Pflanze und Phase und zeigt Datum, Uhrzeit, Auflösung, Dateigröße und Notiz.",
        "Die Pflanzendetailseite zeigt die letzten sechs Aufnahmen und bietet direkten Zugriff auf Kamera und vollständige Galerie.",
        "Für jede Aufnahme entsteht automatisch ein verknüpfter Betriebsjournal-Eintrag; das Foto ist in dessen Detailansicht sichtbar.",
        "Die Lifecycle-Timeline zeigt Fotos als klickbare Kameramarker am jeweiligen Aufnahmedatum.",
        "Ungültige Bilder, Dateien über 12 MB, Zukunftsdaten und Aufnahmen vor Pflanzenstart werden sicher abgewiesen.",
        "Entfernen im Foto-Manager löscht die komprimierte Bilddatei und blendet den Datensatz revisionsfreundlich aus.",
        "Die Fototabelle und der Speicherordner werden beim Anwendungsstart automatisch angelegt; eine manuelle Datenbankmigration ist nicht nötig.",
    ),
    "tests": (
        "python3 tests/regression/check_plant_photo_management.py",
        "python3 tests/regression/check_current_stage_date_correction.py",
        "python3 tests/regression/check_batch_detail_and_journal_sync.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
