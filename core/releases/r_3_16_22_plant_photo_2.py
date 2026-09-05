"""Growstar 3.16.22 / PLANT.PHOTO.2 release metadata."""

RELEASE = {
    "version": "3.16.22",
    "date": "2026-09-05",
    "phase": "PLANT.PHOTO.2",
    "title": "Robuste Fotoansichten und getrennte Bildquellen",
    "summary": (
        "Foto-Manager und Timeline bleiben auch bei einer verzögert "
        "angelegten Fototabelle erreichbar. Kamera und vorhandene Dateien "
        "werden auf Mobilgeräten über zwei eindeutige Schaltflächen geöffnet."
    ),
    "changes": (
        "Der gemeinsame Foto-Lesepfad erkennt eine nach einem unvollständigen Upgrade fehlende Fototabelle und legt sie einmalig selbst an.",
        "Fehler im optionalen Foto-Lesepfad können die zentrale Lifecycle-Timeline nicht mehr mit einem HTTP-500-Fehler blockieren.",
        "Auch Pflanzen- und Journal-Detailansichten bleiben erreichbar, falls das Foto-Subsystem vorübergehend nicht gelesen werden kann.",
        "Der Foto-Manager bleibt bei einem Lesefehler geöffnet, zeigt eine verständliche Meldung und protokolliert die technische Ursache serverseitig.",
        "Die bisher kombinierte Kamera-/Dateiauswahl wurde in 'Foto mit Kamera aufnehmen' und 'Datei oder Galerie auswählen' getrennt.",
        "Nur der Kamera-Eingang verwendet capture=environment; der zweite Eingang öffnet ohne Capture-Vorgabe den mobilen Datei- beziehungsweise Galerie-Dialog.",
        "Nach einer Auswahl wird die jeweils andere Quelle geleert, sodass immer genau ein Foto an das Backend übertragen wird.",
        "Das Backend akzeptiert beide Eingänge über denselben geprüften Komprimierungs- und Dokumentationspfad.",
    ),
    "tests": (
        "python3 tests/regression/check_plant_photo_management.py",
        "python3 tests/regression/check_current_stage_date_correction.py",
        "python3 tests/regression/check_batch_detail_and_journal_sync.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
