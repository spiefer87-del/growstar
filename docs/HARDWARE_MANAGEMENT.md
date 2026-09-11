# Growstar Hardware & Setup

Der eigenständige Hauptmenüpunkt **Hardware & Setup** trennt technische
Infrastruktur von der laufenden Grow-Regelung.

## Struktur

- **Geräte-Manager:** Shelly-Gateways, BLE-Geräte, MQTT-Sensorcontroller,
  Spider-Farmer-Sensoren und die technische GrowCam-Verbindung.
- **Sensoren:** globale Sensorquellen sowie Innen-/Außenzuordnung und
  Kalibrierung je Station.
- **Verbindungen:** Relais, Strom-Aktoren und Controller-Funktionen.
- **Spider Farmer:** GGS-Controller und Power-Strips.
- **Watchdog:** Hardware-Poll, MQTT, Recovery und Safety.
- **Stations-Setup:** Stationen, Shadow/LIVE und Neustartverhalten.
- **Netzwerk, Alarme und Systemstatus:** technische Raspberry-Dienste.

## GrowCam

IP-Adresse, RTSP-Port, Benutzer und RTSP-Pfad werden im Geräte-Manager
gespeichert und benötigen `hardware.configure`. Das Medienmodul verwaltet nur
Livebild, Aufnahmeplan, Stations-/Durchgangszuordnung, Archiv und Zeitraffer.
Beim Speichern einer Seite bleiben die Werte des jeweils anderen Bereichs
unverändert erhalten.
