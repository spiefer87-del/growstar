# VIVOSUN GrowCam C4 lokal in Growstar

Growstar liest die GrowCam C4 (VSC-GCC4) direkt im lokalen Netzwerk. Dafür
wird weder die VIVOSUN-Cloud noch ein VIVOSUN-Kontokennwort benötigt.

## Bestätigte Verbindung

- Kamera-IP: die lokale IPv4-Adresse der Kamera
- RTSP-Port: `554`
- RTSP-Pfad: `/live/ch00_0`
- Benutzer: `admin`
- Kennwort: leer (wird von Growstar nicht gespeichert)
- Transport: RTSP über TCP
- bestätigtes Kamerabild: HEVC, 2560 × 1440 Pixel, 15 Bilder/s

Die Kamera-IP sollte im Router per DHCP-Reservierung fest der GrowCam
zugeordnet werden. Port 554 darf nicht ins Internet weitergeleitet werden.

## Einrichtung

1. In Growstar **Pflanzenmanagement → Kamera** öffnen.
2. Kamera-IP, Port `554`, Pfad `/live/ch00_0`, Benutzer `admin`, Station und
   Standbildintervall eintragen.
3. **Automatische Aufnahmen aktivieren** einschalten und speichern.
4. Mit **Jetzt aufnehmen** die Verbindung sofort prüfen.

Growstar überschreibt bei jeder Aufnahme ausschließlich
`instance/growcam/latest.jpg`. Dadurch entsteht kein unbegrenztes Archiv.
Die lokale Konfiguration liegt mit eingeschränkten Dateirechten unter
`instance/growcam.json`.

## Livestream

Die GrowCam liefert HEVC, das Browser nicht zuverlässig direkt anzeigen.
Growstar transkodiert den Stream deshalb nur während einer geöffneten
Live-Ansicht in MJPEG. Für einen Raspberry Pi 5 werden 960 Pixel Breite und
5 Bilder pro Sekunde empfohlen. Mit **Standbild** wird die Live-Transkodierung
für diesen Browser sofort beendet.

## Durchgang und Zeitraffer

1. Der Kamera einen Pflanzendurchgang zuordnen.
2. **Aufnahmen für Zeitraffer archivieren** aktivieren.
3. Aufnahmeintervall, Aufbewahrungszeit und Video-Bildrate wählen.
4. Nach mindestens zwei Aufnahmen **Video jetzt erstellen** drücken.

Archivbilder und Videos liegen getrennt je Durchgang unter
`instance/growcam/timelapse/batch_<ID>/`. Alte Einzelbilder werden nach der
gewählten Aufbewahrungszeit automatisch entfernt. Bereits erzeugte MP4-Videos
werden auf die fünf neuesten Videos je Durchgang begrenzt. Die MP4-Erstellung läuft im Hintergrund, damit der
Growstar-Webserver währenddessen erreichbar bleibt.

## Diagnose auf dem Raspberry Pi

```bash
timeout 12 ffprobe \
  -v error \
  -rtsp_transport tcp \
  -select_streams v:0 \
  -show_entries stream=codec_name,width,height,r_frame_rate \
  -of default=noprint_wrappers=1 \
  'rtsp://admin:@192.168.178.122:554/live/ch00_0'
```

Die Beispiel-IP ist durch die tatsächliche reservierte Kamera-IP zu ersetzen.
