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

Die Bridge lauscht auf TCP/TLS Port 18883. Port 8000 bleibt
bewusst Growstars Gunicorn-Webbackend vorbehalten; beide Dienste können daher
parallel laufen. Erst in einem folgenden Netzwerkschritt wird entschieden, ob
der GGS-Controller über

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


## SF.1N – isoliertes GGS-Netzwerk

Ab Growstar 3.11.1 wird der reale GGS-Verkehr über einen separaten, kontrollierten
NetworkManager-Access-Point geführt:

    eth0 -> FRITZ!Box / Heimnetz / Internet
    wlan0 -> Growstar-SF (10.42.77.0/24, 2.4 GHz, WPA2)

NetworkManager stellt für `Growstar-SF` DHCP/DNS und die normale Internetfreigabe
bereit (`ipv4.method shared`). Growstar verändert dafür kein bestehendes Heim-WLAN-
Profil und löscht keine Verbindungen.

Der zusätzliche nftables-Schutz ist bewusst eng:

- Nur TCP/8883, das **von wlan0** kommt, wird auf die lokale read-only Bridge 18883 umgeleitet.
- Die Bridge selbst verbindet sich über eth0 normal mit `sf.mqtt.spider-farmer.com:8883`;
  ihr eigener Upstream wird dadurch nicht erneut umgeleitet.
- Geräte im `Growstar-SF`-WLAN dürfen nicht in RFC1918-Privatnetze weiterleiten.
- Am Raspberry selbst sind vom Spider-Farmer-WLAN nur DHCP, DNS, ICMP-Ping und die Bridge erreichbar;
  Growstar-Weboberfläche und SSH werden dort nicht freigegeben.
- IPv6 ist für das isolierte GGS-WLAN deaktiviert.

Vor jedem AP-Start prüft der Root-Dienst:

1. `eth0` ist verbunden und besitzt IPv4.
2. Die Default-Route läuft über `eth0`.
3. Auch die Spider-Farmer-Cloud würde über `eth0` geroutet.
4. `wlan0` ist AP-fähig.
5. Growstars festes Geräte-Provisionierungs-WLAN ist gesetzt und besitzt ein gespeichertes Secret.
6. Das Shelly-Provisionierungsziel ist **nicht** `Growstar-SF`.

Bei einem Fehler während der Umschaltung entfernt Growstar seine nftables-Regeln,
deaktiviert den AP und versucht das vorherige wlan0-Profil wiederherzustellen.

Installation ist absichtlich zweistufig:

    sudo bash install/install_spiderfarmer_network.sh

Das installiert nur Helper, Konfiguration und systemd-Unit. Der AP bleibt aus.
Erst nach erfolgreichem Preflight wird bewusst gestartet:

    sudo systemctl start growstar-spiderfarmer-network.service

Status:

    sudo /usr/local/libexec/growstar-spiderfarmer-network status \
      --config ~/growstar/instance/spiderfarmer_network/config.json \
      --state ~/growstar/instance/spiderfarmer_network/state.json \
      --project-dir ~/growstar

Die zufällig erzeugten Zugangsdaten für `Growstar-SF` werden nicht automatisch in
Logs ausgegeben. Sie können lokal mit `sudo ... credentials` angezeigt werden und
sollten nicht in Screenshots oder Support-Nachrichten veröffentlicht werden.
