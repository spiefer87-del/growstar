"""Growstar 3.16.34 / PLANT.CAMERA.1 release metadata."""

RELEASE = {
    "version": "3.16.34",
    "date": "2026-09-10",
    "phase": "PLANT.CAMERA.1",
    "title": "VIVOSUN GrowCam C4 direkt im lokalen Netzwerk",
    "summary": (
        "Growstar zeigt das aktuelle 2K-Bild einer VIVOSUN GrowCam C4 "
        "direkt per lokalem RTSP an und aktualisiert es automatisch."
    ),
    "changes": (
        "Die Pflanzenverwaltung erhält eine eigene Kamera-Seite mit aktuellem Bild, Verbindungsstatus und manueller Aufnahme.",
        "Kamera-IP, Station, RTSP-Pfad und Aufnahmeintervall lassen sich rollenbasiert in Growstar konfigurieren.",
        "Der Snapshot-Dienst liest die bestätigte GrowCam-C4-Adresse per RTSP über TCP und FFmpeg.",
        "Aufnahmen werden als validiertes JPEG atomar veröffentlicht; ein fehlgeschlagener Abruf ersetzt niemals das letzte gültige Bild.",
        "Growstar verwendet ausschließlich eine lokale IPv4-Adresse und speichert weder VIVOSUN-Konto noch Kamera- oder Cloud-Passwort.",
        "Ein einzelnes latest.jpg verhindert unkontrolliertes Wachstum des Bildspeichers.",
    ),
    "tests": (
        "python3 tests/regression/check_growcam_integration.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
        "python3 -m compileall -q app.py services/growcam.py routes/camera.py core/releases/r_3_16_34_plant_camera_1.py",
    ),
}
