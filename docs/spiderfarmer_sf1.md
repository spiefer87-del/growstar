# Spider Farmer Integration – Phase SF.1

## Ziel

SF.1 installiert eine **read-only transparente TLS/MQTT-Bridge** als separaten
Systemdienst. Sie soll zuerst zeigen, welche Frames die echte Spider-Farmer-
Hardware des Growstar-Systems sendet, bevor irgendein Growstar-Schreibzugriff
implementiert wird.

## Sicherheitsgrenze

SF.1 besitzt keinen Command-Encoder und erzeugt keine MQTT-PUBLISH-Pakete.
Der Dienst kann daher aus Growstar heraus weder Outlet-, Lüfter- noch
Lichtbefehle erzeugen.

Bereits vorhandene Kommunikation wird nur transparent weitergeleitet:

    GGS Controller -> Growstar SF.1 -> Spider Farmer Cloud
    GGS Controller <- Growstar SF.1 <- Spider Farmer Cloud

Dadurch kann die offizielle Spider-Farmer-App weiterhin Befehle senden. SF.1
zeichnet diese Cloud->Controller-Frames ebenfalls lokal auf. Das ist für die
spätere sichere Implementierung von Dimmen, Outlet-Steuerung und Lüfterstufen
besonders wertvoll.

## Keine Netzwerkänderung in SF.1

Der Installer verändert ausdrücklich nicht:

- NetworkManager
- WLAN-Profile
- DNS
- nftables/iptables
- IP-Forwarding
- Mosquitto

Die Bridge lauscht standardmäßig auf TCP/TLS Port 8000. Erst in einem folgenden
Netzwerkschritt wird entschieden, ob der GGS-Controller über

1. Router/NAT/DNS-Redirect oder
2. einen dedizierten Growstar-Spider-Farmer-Hotspot

auf diesen Listener geführt wird.

Für eine produktive Growstar-Appliance ist ein separates Netzwerkinterface
(Ethernet + WLAN oder WLAN + USB-WLAN) die bevorzugte Lösung.

## Lokale Diagnosedaten

Die Bridge schreibt ausschließlich unter:

    instance/spiderfarmer/

Dateien:

- `bridge_state.json` – kleiner Status-/Session-Snapshot
- `raw_frames.jsonl` – vollständige MQTT-Anwendungsframes
- `raw_frames.jsonl.1` – eine rotierte Vorgängerdatei

Die Dateien werden mit restriktiven Rechten erzeugt. Die Rohframes können
MAC-Adressen, UIDs und Geräte-/Zeitplan-Konfiguration enthalten. Nicht
unredigiert veröffentlichen.

## Installation nach GitHub-Upload und Git-Pull

Konfiguration prüfen, noch ohne Start:

    cd ~/growstar
    sudo bash install/install_spiderfarmer_bridge.sh

Danach kann geprüft werden:

    /usr/bin/python3 -m bridge.spiderfarmer.main --check
    systemctl status growstar-spiderfarmer --no-pager

Der Dienst bleibt in diesem Modus deaktiviert.

Erst wenn die Netzwerkführung vorbereitet ist:

    sudo bash install/install_spiderfarmer_bridge.sh --start

Logs:

    sudo journalctl -u growstar-spiderfarmer -f

Rohframes:

    tail -f ~/growstar/instance/spiderfarmer/raw_frames.jsonl

## Was wir mit den ersten echten Frames prüfen

Für die nächsten Phasen interessieren besonders:

- `getDevSta`
- `getConfigField`
- `getConfigFile`
- `device.light` / `device.light2`
- `mOnOff`
- `mLevel`
- `modeType`
- `sensor.temp`
- `sensor.humi`
- `sensor.co2`
- `sensor.ppfd`
- `ps5` / `outlet`
- Bodensensorblöcke

Wenn in der offiziellen Spider-Farmer-App die Helligkeit geändert wird, zeichnet
SF.1 den Cloud->Controller-Befehl mit auf. Dadurch kann Growstar SF.5 später die
Dimmfunktion gegen die **eigene echte Hardware** verifizieren statt nur fremde
Packet-Captures zu übernehmen.
