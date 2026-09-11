# Growstar Medien-Explorer

Der Medien-Explorer unter **Pflanzenmanagement → Medien** zeigt ausschließlich
Dateien, die Growstar selbst verwaltet. Betriebssystemdateien, Datenbanken und
Protokolle bleiben außerhalb der Löschoberfläche.

## Speicherstruktur

- `instance/growcam/latest.jpg`: aktuelles Kamera-Standbild, wird ersetzt.
- `instance/growcam/timelapse/batch_<ID>/frame-*.jpg`: Zeitrafferbilder je Durchgang.
- `instance/growcam/timelapse/batch_<ID>/thumbnails/`: kleine Galerie-Vorschauen.
- `instance/growcam/timelapse/batch_<ID>/timelapse-*.mp4`: erzeugte Videos.
- `instance/plant_photos/*.jpg`: optimierte Pflanzen- und Durchgangsfotos; die
  Zuordnung und Metadaten liegen in der Growstar-Datenbank.

## Aufbewahrung

Zeitrafferbilder werden entsprechend der Kameraeinstellung nach 30 bis 365
Tagen automatisch bereinigt. Für Videos gilt je Durchgang eine sichtbare Grenze
von 5, 10, 25, 50 oder 100 Videos. `Unbegrenzt` deaktiviert die automatische
Video-Bereinigung; die Dateien müssen dann im Explorer manuell kontrolliert
werden. Standard sind 25 Videos je Durchgang.

Pflanzen- und Durchgangsfotos werden nicht automatisch gelöscht. Eine Löschung
im Explorer oder Foto-Manager entfernt den Datensatz kontrolliert und danach die
zugehörige Bilddatei. Alle Löschaktionen erfordern eine ausdrückliche
Bestätigung und die Berechtigung `plants.edit`.

## Downloads

Videos, Zeitrafferbilder, Pflanzenfotos und Durchgangsfotos besitzen einen Download-Schalter.
Der normale Klick auf ein Vorschaubild öffnet beziehungsweise spielt das Medium
ab; der Download wird als Anlage mit einem sicheren Growstar-Dateinamen
ausgeliefert.
