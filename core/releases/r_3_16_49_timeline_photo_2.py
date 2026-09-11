"""Growstar 3.16.49 / TIMELINE.PHOTO.2 release metadata."""

RELEASE = {
    "version": "3.16.49",
    "date": "2026-09-11",
    "phase": "TIMELINE.PHOTO.2",
    "title": "Erreichbarer Schließen-Schalter der Timeline-Galerie",
    "summary": (
        "Der mobile Schließen-Schalter liegt jetzt gut sichtbar in einem eigenen "
        "unteren Bedienbereich und die Vollbildgalerie überdeckt die feste Kopfzeile."
    ),
    "changes": [
        "Der Schließen-Schalter wurde aus der oberen Ecke in den unteren Galeriebereich verlegt.",
        "Eine breite, beschriftete Touch-Fläche verbessert die Bedienung auf Mobilgeräten.",
        "Die Vollbildgalerie liegt nun über der festen Growstar-Kopfzeile.",
        "Wisch-, Pfeil-, Escape- und Browser-Zurück-Navigation bleiben unverändert erhalten.",
    ],
    "tests": [
        "python3 tests/regression/check_timeline_lightbox_close.py",
        "python3 tests/regression/check_timeline_plant_photo_gallery.py",
        "python3 tests/regression/check_photo_gallery_navigation.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
