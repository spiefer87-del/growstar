"""Growstar 3.16.36 / PLANT.CAMERA.3 release metadata."""

RELEASE = {
    "version": "3.16.36",
    "date": "2026-09-10",
    "phase": "PLANT.CAMERA.3",
    "title": "GrowCam-Maximalmodus und Zeitraffer-Studio",
    "summary": (
        "Growstar nutzt auf Wunsch das bestätigte GrowCam-Maximum von "
        "2560 × 1440 bei 15 Bildern pro Sekunde und erweitert den Zeitraffer "
        "um Bildkontrolle, Löschung und Ausgabeprofile."
    ),
    "changes": (
        "Der lokale Live-Proxy unterstützt jetzt bis zu 2560 Pixel Breite und 15 Bilder pro Sekunde.",
        "Ein Klick auf das Livebild öffnet eine Vollbildansicht mit Zoom bis 500 Prozent und verschiebbarem Bildausschnitt.",
        "Live-Frames bleiben flüchtig im Arbeitsspeicher und werden weiterhin nicht als Aufnahmen gespeichert.",
        "Das Zeitrafferarchiv zeigt paginierte Vorschaubilder und öffnet jedes Originalbild einzeln.",
        "Ungeeignete Zeitrafferbilder können mit Bestätigung gezielt aus dem jeweiligen Durchgang entfernt werden.",
        "Die Zeitraffer-Bildrate befindet sich jetzt zusammen mit Ausgabeauflösung und Kompressionsstufe direkt im Video-Erstellungsformular.",
        "Vorschaubilder werden platzsparend erzeugt; Originalaufnahmen bleiben für hochwertige Videos erhalten.",
    ),
    "tests": (
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
        "python3 -m compileall -q services/growcam.py routes/camera.py core/releases/r_3_16_36_plant_camera_3.py",
    ),
}
