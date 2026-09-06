"""Growstar 3.16.27 / PLANT.PHOTO.5 release metadata."""

RELEASE = {
    "version": "3.16.27",
    "date": "2026-09-06",
    "phase": "PLANT.PHOTO.5",
    "title": "Filter bleiben beim Schliessen der Fotogalerie erhalten",
    "summary": (
        "Die Vollbildgalerie besitzt jetzt einen eigenen Browser-Verlaufseintrag. "
        "Android-Zurueck schliesst dadurch zuerst das Foto, ohne auf die vorherige "
        "ungefilterte Foto-Manager-URL zu wechseln."
    ),
    "changes": (
        "Das Oeffnen eines Fotos legt einen Galerie-Verlaufseintrag auf der unveraenderten Filter-URL an.",
        "Browser- und Android-Zurueck schliessen zuerst die Vollbildgalerie.",
        "Pflanzen-, Phasen- und Durchgangsfilter bleiben nach dem Schliessen erhalten.",
        "Schliessen-Schaltflaeche und Escape entfernen denselben Galerie-Verlaufseintrag sauber.",
        "Der aktuelle Bildindex wird beim Wischen und Blaettern im Verlauf aktualisiert.",
        "Browser-Vorwaerts kann die geschlossene Galerie wieder beim zuletzt betrachteten Bild oeffnen.",
        "Die Galeriemenge bleibt weiterhin strikt an die serverseitig gefilterten Bildkarten gebunden.",
    ),
    "tests": (
        "python3 tests/regression/check_photo_gallery_filter_history.py",
        "python3 tests/regression/check_photo_gallery_navigation.py",
        "python3 tests/regression/check_plant_photo_management.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
