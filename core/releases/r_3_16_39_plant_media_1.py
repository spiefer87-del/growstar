"""Growstar 3.16.39 / PLANT.MEDIA.1 release metadata."""

RELEASE = {
    "version": "3.16.39",
    "date": "2026-09-11",
    "phase": "PLANT.MEDIA.1",
    "title": "Medien-Explorer für Videos und Pflanzendokumentation",
    "summary": (
        "Growstar bündelt Zeitraffer-Videos, Pflanzenfotos und Durchgangsfotos "
        "in einer speicherbewussten Medienverwaltung mit Vorschau, Download und Löschung."
    ),
    "changes": [
        "Der neue Medien-Explorer visualisiert GrowCam- und Fotoordner, Dateimengen, Mediengröße sowie freien Raspberry-Speicher.",
        "Zeitraffer-Videos können direkt angesehen, heruntergeladen und nach Bestätigung einzeln gelöscht werden.",
        "Pflanzen- und Durchgangsfotos erhalten Downloads im Foto-Manager und im seitenweise aufgebauten Medien-Explorer.",
        "Die bisher feste Grenze von fünf Videos wird durch eine sichtbare Aufbewahrung von 5, 10, 25, 50, 100 oder unbegrenzt ersetzt.",
    ],
    "tests": [
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_plant_photo_management.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
        "python3 -m compileall -q services/growcam.py plant_management/photos.py routes/camera.py routes/plant_management.py core/releases/r_3_16_39_plant_media_1.py",
    ],
}
