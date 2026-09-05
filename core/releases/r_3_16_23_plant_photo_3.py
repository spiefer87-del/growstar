"""Growstar 3.16.23 / PLANT.PHOTO.3 release metadata."""

RELEASE = {
    "version": "3.16.23",
    "date": "2026-09-05",
    "phase": "PLANT.PHOTO.3",
    "title": "Fotodokumentation für vollständige Durchgänge",
    "summary": (
        "Gesamtaufnahmen eines Zelts können jetzt einem vollständigen "
        "Durchgang zugeordnet, komprimiert gespeichert und getrennt von "
        "den Fotos einzelner Pflanzen verwaltet werden."
    ),
    "changes": (
        "Durchgangsfotos werden in einer eigenen Datenbanktabelle mit Aufnahmezeit, Notiz, Bildmaßen, Dateigröße und revisionsfähigen Benutzerangaben gespeichert.",
        "Kamera und mobile Datei- beziehungsweise Galerieauswahl stehen auch für Durchgangsfotos als getrennte Eingänge bereit.",
        "Neue Gesamtaufnahmen werden automatisch verkleinert, als bereinigtes JPEG gespeichert und dem ausgewählten Durchgang zugeordnet.",
        "Der Foto-Manager besitzt getrennte Bereiche und Filter für Pflanzenfotos und Durchgangsfotos.",
        "Die Durchgangsdetailseite zeigt die letzten Gesamtaufnahmen und bietet direkte Aktionen für Aufnahme und vollständige Galerie.",
        "Für jedes Durchgangsfoto entsteht automatisch ein verknüpfter Betriebsjournal-Eintrag; die Journal-Detailseite zeigt das zugehörige Bild.",
        "Durchgangsfotos werden bewusst nicht an Pflanzen gebunden und erscheinen daher nicht in der Pflanzen-Timeline.",
        "Fehlende Durchgangsfoto-Tabellen werden über denselben robusten Initialisierungspfad wie Pflanzenfotos selbständig nachgezogen.",
    ),
    "tests": (
        "python3 tests/regression/check_plant_photo_management.py",
        "python3 tests/regression/check_batch_detail_and_journal_sync.py",
        "python3 tests/regression/check_current_stage_date_correction.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
