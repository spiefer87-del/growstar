"""Growstar 3.16.28 / PLANT.PROPAGATION.1 release metadata."""

RELEASE = {
    "version": "3.16.28",
    "date": "2026-09-06",
    "phase": "PLANT.PROPAGATION.1",
    "title": "Fehlerhafte Vermehrungsansaetze sicher entfernen",
    "summary": (
        "Berechtigte Benutzer koennen irrtuemlich doppelt angelegte "
        "Vermehrungsansaetze nach einer Bestaetigung entfernen. Saatgut wird "
        "korrekt zurueckgebucht und bestehende Pflanzenherkuenfte bleiben geschuetzt."
    ),
    "changes": (
        "Die Ansatz-Detailseite besitzt fuer plants.edit den neuen Schalter Ansatz entfernen.",
        "Eine eindeutige Sicherheitsabfrage nennt Ansatzcode und Anzahl der Einheiten.",
        "Ansatz und noch ungenutzte Einheiten werden gemeinsam in einer Transaktion entfernt.",
        "Bei Samenansaetzen wird die zugehoerige automatische Saatgutentnahme rueckgaengig gemacht.",
        "Ein zuvor leerer Saatgut-Lot wird nach der Rueckbuchung wieder als verfuegbar markiert.",
        "Ansaetze mit bereits erzeugten Pflanzen koennen wegen der Herkunftskette nicht geloescht werden.",
        "Jede erfolgreiche Korrektur wird in Audit und Betriebsjournal dokumentiert.",
        "Die Route ist durch plants.edit, CSRF und einen serverseitig geprueften Bestaetigungscode geschuetzt.",
    ),
    "tests": (
        "python3 tests/regression/check_propagation_run_removal.py",
        "python3 tests/regression/check_photo_gallery_filter_history.py",
        "python3 tests/regression/check_plant_photo_management.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
