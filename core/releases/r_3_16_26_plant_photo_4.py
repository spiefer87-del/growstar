"""Growstar 3.16.26 / PLANT.PHOTO.4 release metadata."""

RELEASE = {
    "version": "3.16.26",
    "date": "2026-09-06",
    "phase": "PLANT.PHOTO.4",
    "title": "Gefilterte Wischgalerie im Foto-Manager",
    "summary": (
        "Der Foto-Manager ist jetzt direkt ueber die Hauptnavigation erreichbar "
        "und zeigt Pflanzen- sowie Durchgangsfotos in einer filtergebundenen "
        "Vollbildgalerie mit Wisch- und Tastatursteuerung."
    ),
    "changes": (
        "Pflanzenmanagement besitzt den neuen Navigationseintrag Fotos mit eindeutigem Aktivstatus.",
        "Ein Klick auf ein Foto oeffnet eine interne Vollbildansicht statt des Rohbilds in einem neuen Browser-Tab.",
        "Vorheriges und naechstes Foto sind ueber sichtbare Schaltflaechen erreichbar.",
        "Horizontale Wischgesten ermoeglichen die Daumenbedienung auf Smartphones und Tablets.",
        "Pfeiltasten wechseln das Bild; Escape und der Schliessen-Schalter beenden die Galerie.",
        "Die Galerie wird ausschliesslich aus den aktuell gefilterten Seitentreffern aufgebaut.",
        "Pflanzen-, Phasen- und Durchgangsfilter begrenzen dadurch auch das Blaettern in der Vollbildansicht.",
        "Bildtitel, Aufnahmezeit, Phase beziehungsweise Durchgang und Notiz bleiben in der Grossansicht sichtbar.",
    ),
    "tests": (
        "python3 tests/regression/check_photo_gallery_navigation.py",
        "python3 tests/regression/check_plant_photo_management.py",
        "python3 tests/regression/check_app_shell_navigation.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
