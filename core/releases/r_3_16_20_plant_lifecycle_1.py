"""Growstar 3.16.20 / PLANT.LIFECYCLE.1 release metadata."""

RELEASE = {
    "version": "3.16.20",
    "date": "2026-09-05",
    "phase": "PLANT.LIFECYCLE.1",
    "title": "Bestätigte Korrektur des aktuellen Phasenstarts",
    "summary": (
        "Das Startdatum der bereits laufenden Pflanzenphase kann nach einer "
        "expliziten Bestätigung korrigiert werden. Growstar hält dabei den "
        "vorherigen Phasenabschluss, die Timeline und die Ernteprognose synchron."
    ),
    "changes": (
        "Die Lifecycle-Steuerung zeigt das gespeicherte Startdatum der aktuellen Phase direkt im Datumsfeld.",
        "Wird dieselbe Phase mit einem abweichenden Datum gespeichert, erscheint eine konkrete Sicherheitsabfrage mit altem und neuem Datum.",
        "Ohne übermittelten Bestätigungsnachweis lehnt auch das Backend die Datumskorrektur ab.",
        "Nach Bestätigung wird der bestehende offene Phaseneintrag korrigiert, statt eine doppelte Phase anzulegen.",
        "Das Enddatum der unmittelbar vorherigen Phase wird atomar auf dieselbe neue Phasengrenze gesetzt.",
        "Timeline, Phasentage, Blütebeginn und dynamische Ernteprognose verwenden nach dem Laden sofort das korrigierte Datum.",
        "Eine optionale Notiz wird als Datumskorrektur am Phasenereignis ergänzt, ohne die bisherige Notiz zu verlieren.",
        "Die Änderung wird zusätzlich im Audit und als systemischer Betriebsjournal-Eintrag dokumentiert.",
        "Unveränderte Daten erzeugen keine Scheinkorrektur.",
        "Korrekturen vor den Beginn der vorherigen Phase und Datumswerte in der Zukunft werden sicher abgewiesen.",
        "Beim echten Wechsel in eine andere Phase setzt die Oberfläche weiterhin das heutige Datum als sinnvollen Vorschlag.",
    ),
    "tests": (
        "python3 tests/regression/check_current_stage_date_correction.py",
        "python3 tests/regression/check_classic_vpd_and_harvest_forecast.py",
        "python3 tests/regression/check_batch_detail_and_journal_sync.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
