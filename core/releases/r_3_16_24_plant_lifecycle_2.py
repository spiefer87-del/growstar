"""Growstar 3.16.24 / PLANT.LIFECYCLE.2 release metadata."""

RELEASE = {
    "version": "3.16.24",
    "date": "2026-09-05",
    "phase": "PLANT.LIFECYCLE.2",
    "title": "Startdatum jeder Pflanzenphase nachträglich korrigieren",
    "summary": (
        "Jede bereits gespeicherte Phase besitzt im Phasenverlauf eine eigene "
        "berechtigungsgeschützte Datumskorrektur. Die Lifecycle-Steuerung "
        "darunter dient wieder ausschließlich neuen Phasenwechseln."
    ),
    "changes": (
        "Neben jeder Phase im Lifecycle-Verlauf steht für Benutzer mit plants.edit-Berechtigung ein kompakter Ändern-Button bereit.",
        "Der eingeblendete Dialog übernimmt das gespeicherte Startdatum und verlangt vor dem Speichern eine ausdrückliche Bestätigung.",
        "Startdaten können sowohl für die aktuelle als auch für bereits abgeschlossene historische Phasen korrigiert werden.",
        "Beim Verschieben einer Phasengrenze wird das Enddatum der vorherigen Phase atomar mitgeführt.",
        "Die Korrektur der ersten Phase aktualisiert zusätzlich das Startdatum der Pflanze.",
        "Eine Phase kann weder vor ihren Vorgänger noch hinter den Beginn ihrer Folgephase verschoben werden.",
        "Jede Korrektur wird im Audit-Trail und automatisch im Betriebsjournal dokumentiert.",
        "Der bisher kombinierte Bereich 'Phase wechseln oder korrigieren' wurde wieder auf einen reinen Phasenwechsel reduziert.",
    ),
    "tests": (
        "python3 tests/regression/check_current_stage_date_correction.py",
        "python3 tests/regression/check_plant_photo_management.py",
        "python3 tests/regression/check_batch_detail_and_journal_sync.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
