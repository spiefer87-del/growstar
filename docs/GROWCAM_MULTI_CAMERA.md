# GrowCam-Mehrkamera-Verwaltung

Growstar verwaltet VIVOSUN GrowCam C4 ab Version 3.16.43 als eigenständige
Kamera-Registry. Es gibt keine fest codierte Obergrenze für die Anzahl der
Kameras. Pro Station wird eine Kamera zugeordnet, damit das jeweilige
Grow-Control-Dashboard eindeutig seinen LIVE-Einstieg anzeigen kann.

## Neue Kamera hinzufügen

1. **Hardware & Setup → Geräte → GrowCam-Verbindungen** öffnen.
2. Lokale IPv4-Adresse der Kamera eintragen.
3. Station auswählen.
4. **Kamera hinzufügen und aktivieren** wählen.

Growstar setzt die bestätigten Standardwerte automatisch:

- RTSP-Port `554`
- RTSP-Pfad `/live/ch00_0`
- Benutzer `admin`
- leeres Kamerapasswort, das nicht gespeichert wird
- Live-Auflösung `2560 px` und `15 Bilder/s`

Anschließend lässt sich die Kamera sofort im Medienmodul auswählen. Im
Dashboard der zugeordneten Station erscheint der LIVE-Einstieg automatisch.

## Daten und Migration

Die bestehende Kamera wird automatisch zu `camera_1`. Ihr historischer Ordner
`instance/growcam/` bleibt unverändert. Weitere Kameras erhalten getrennte
Unterordner, beispielsweise `instance/growcam/camera_2/`. Standbilder,
Zeitrafferbilder, Videos, Fehlerstatus und parallele Live-Zuschauer werden je
Kamera getrennt geführt.

Eine Kamera lässt sich im Medienmodul deaktivieren, ohne ihre Konfiguration oder
ihre bisherigen Aufnahmen zu verlieren.
