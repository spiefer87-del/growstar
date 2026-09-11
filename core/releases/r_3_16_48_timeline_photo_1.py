"""Growstar 3.16.48 / TIMELINE.PHOTO.1 release metadata."""

RELEASE = {
    "version": "3.16.48",
    "date": "2026-09-11",
    "phase": "TIMELINE.PHOTO.1",
    "title": "Pflanzenbezogene Fotogalerie in der Timeline",
    "summary": (
        "Timeline-Fotomarker öffnen eine interne Vollbildgalerie, in der ausschließlich "
        "die chronologisch sortierten Aufnahmen der angeklickten Pflanze durchblättert werden."
    ),
    "changes": [
        "Ein Timeline-Foto öffnet die bestehende mobile Vollbilddarstellung statt eines neuen Rohbild-Tabs.",
        "Vor, zurück und Wischgesten bleiben immer auf die angeklickte Pflanze begrenzt.",
        "Die Reihenfolge folgt Aufnahmezeit und Foto-ID vom ältesten zum neuesten Bild.",
        "Pfeiltasten, Escape sowie Browser- und Android-Zurück werden unterstützt.",
    ],
    "tests": [
        "python3 tests/regression/check_timeline_plant_photo_gallery.py",
        "python3 tests/regression/check_photo_gallery_navigation.py",
        "python3 tests/regression/check_photo_gallery_filter_history.py",
        "python3 tests/regression/check_plant_photo_management.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
