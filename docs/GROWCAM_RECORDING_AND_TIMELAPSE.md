# GrowCam Videoaufnahme und Zeitraffer

Ab Growstar 3.16.44 sind die Medienfunktionen sichtbar getrennt:

- **Kamera**: Livebild, Standbild, Kameraeinstellungen und direkte Videoaufnahme
- **Zeitraffer**: automatischer Aufnahmeplan, Durchgangsarchiv und Videoerstellung
- **Explorer**: Videoaufnahmen, Zeitraffer-Videos, Archivbilder und Pflanzenfotos

## Direkte Videoaufnahme

In der Kameraansicht werden Kamera, Dauer und Pflanzendurchgang ausgewählt. Die
verfügbaren Laufzeiten reichen von 30 Sekunden bis 10 Minuten. Growstar kopiert
den originalen 2K-RTSP-Videostream in eine MP4-Datei, ohne ihn erneut zu
komprimieren. Das hält CPU-Auslastung und Qualitätsverlust gering.

Die Dateien liegen getrennt nach Kamera und Durchgang unter:

`instance/growcam/<Kamera>/recordings/batch_<Durchgang>/`

Im Medien-Explorer können sie abgespielt, heruntergeladen und gelöscht werden.

## Pflanzenfoto aus der GrowCam

Unter **Medien → Foto-Manager → Pflanzenfoto aufnehmen** kann eine aktive
GrowCam als Quelle gewählt werden. Beim Speichern erstellt Growstar ein frisches
Standbild, optimiert es auf das normale Pflanzenfoto-Format, ordnet es der
gewählten Pflanze und Pflanzenphase zu und erzeugt den üblichen Journaleintrag.

## Zeitraffer

Das eigene Zeitraffer-Modul enthält die Kamera- und Durchgangsauswahl, das
Archivintervall, die Aufbewahrungszeit sowie Bildrate, Auflösung und Kompression
für das daraus erzeugte Video. Mehrere Zelte und Kameras bleiben vollständig
voneinander getrennt.
