"""Growstar 3.16.19 / PLANT.BATCH.1 release metadata."""

RELEASE = {
    "version": "3.16.19",
    "date": "2026-09-05",
    "phase": "PLANT.BATCH.1",
    "title": "Durchgangsdetails und automatische Journal-Zuordnung",
    "summary": (
        "Durchgänge erhalten eine eigene Detailseite mit aktuellem und "
        "historischem Pflanzenbestand. Im Betriebsjournal markiert die Auswahl "
        "eines Durchgangs automatisch dessen zugeordnete Pflanzen."
    ),
    "changes": (
        "Die Durchgangstabelle öffnet per Name, Code, Zeile oder Öffnen-Link eine neue Detailseite.",
        "Die Tabellenzeilen sind zusätzlich per Eingabetaste und Leertaste bedienbar.",
        "Das Durchgangsdetail zeigt Code, Status, Start, Standort sowie Gesamt- und Aktivzahl.",
        "Alle aktuell oder historisch zugeordneten Pflanzen werden mit Sorte, Phase, Rolle, Status und Standort dargestellt.",
        "Pflanzennamen führen direkt zum jeweiligen Pflanzendetail; eine gefilterte Gesamtliste bleibt erreichbar.",
        "Die letzten acht Betriebsereignisse des Durchgangs werden auf der Detailseite eingeblendet.",
        "Ein neuer Betriebsjournal-Eintrag kann mit bereits vorausgewähltem Durchgang gestartet werden.",
        "Wird im Journalformular ein Durchgang ausgewählt, markiert Growstar dessen sichtbare Pflanzen automatisch.",
        "Mehrere Durchgänge bilden die Vereinigungsmenge ihrer Pflanzen; manuelle Ergänzungen und bewusste Abwahlen bleiben möglich.",
        "Beim Entfernen eines Durchgangs werden nur rein automatisch gesetzte Pflanzenauswahlen zurückgenommen.",
        "Eine Live-Rückmeldung nennt die Zahl automatisch ausgewählter Pflanzen und Durchgänge.",
        "Durchgangschips in Journalübersicht und Journaldetail verlinken ebenfalls die neue Detailansicht.",
        "Die bisherige Durchgangsbearbeitung bleibt unter einer eindeutigen /bearbeiten-Adresse erhalten.",
    ),
    "tests": (
        "python3 tests/regression/check_batch_detail_and_journal_sync.py",
        "python3 tests/regression/check_energy_navigation_category.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
