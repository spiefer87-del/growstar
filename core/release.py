"""Zentrale Growstar-Release- und Patch-Informationen.

Wichtig:
- Die aktuelle Version wird ausschließlich vom ersten RELEASES-Eintrag
  abgeleitet.
- Für einen neuen Patch wird ein neuer Eintrag oben ergänzt.
- Regelung, Hardware und Runtime greifen auf dieses Modul nicht zu.
"""

from __future__ import annotations

from copy import deepcopy
import datetime


RELEASES = (
    {
        "version": "3.7.4",
        "date": "2026-08-17",
        "phase": "4S.3.1",
        "title": "Stabiler WLAN-Scan und zuverlässiger Netzwerk-Helper",
        "summary": (
            "Der erzwungene WLAN-Scan wartet jetzt auf das fertige "
            "NetworkManager-Ergebnis. Schreibende Netzwerkaktionen werden nicht "
            "mehr von der Polkit-Zuordnung des Gunicorn-Prozesses abhängig gemacht, "
            "sondern über einen eng begrenzten root-eigenen Helper ausgeführt."
        ),
        "changes": (
            "Ein manueller WLAN-Refresh fordert zuerst explizit einen NetworkManager-Scan an und liest die Access-Point-Liste erst nach einer Wartephase.",
            "Der Refresh verwendet für die abschließende Liste --rescan no, damit kein zweiter paralleler Scan ein frühes Zwischenergebnis erzeugt.",
            "Die bestehende WLAN-Liste bleibt im Browser sichtbar, während der neue Scan läuft; der Button zeigt 'Scan läuft …'.",
            "Die fragile Phase-4S.3-Polkit-Freigabe für den Gunicorn-Prozess wird durch einen root-eigenen Netzwerk-Helper ersetzt.",
            "Flask und Gunicorn bleiben weiterhin vollständig unprivilegiert.",
            "sudoers erlaubt dem Growstar-Dienstbenutzer ausschließlich den fest installierten Netzwerk-Helper ohne Passwortabfrage.",
            "Der Helper prüft zusätzlich seinen systemd-Cgroup-Kontext und verweigert Aufrufe außerhalb von growstar.service.",
            "Der Helper akzeptiert nur fest implementierte JSON-Aktionen und führt nmcli weiterhin ohne Shell-Ausführung aus.",
            "WLAN-Passwörter werden per stdin weitergereicht und erscheinen weder im Helper- noch im nmcli-Prozessargument.",
            "WLAN-Verbindung und Rollback werden vollständig im privilegierten Helper ausgeführt.",
            "Neue WLAN-Profile werden bewusst systemweit angelegt, damit NetworkManager sie auf einem headless Growstar bereits beim Boot automatisch verbinden kann.",
            "Der Installer entfernt die alte /etc/polkit-1/rules.d/49-growstar-network.rules automatisch.",
            "Der automatische Erstinbetriebnahme-Hotspot bleibt weiterhin deaktiviert, bis ein kontrollierter WLAN-Wechsel erfolgreich getestet wurde.",
        ),
        "tests": (
            "Netzwerkseite öffnen: ein frischer Scan darf nach Abschluss nicht nur das aktuell verbundene WLAN anzeigen, wenn weitere Netze sichtbar sind.",
            "Auf 'Aktualisieren' drücken: während des Scans bleibt die bisherige Liste sichtbar und der Button zeigt 'Scan läuft …'.",
            "Capabilities-API meldet nach Helper-Installation write_ready=true und backend=privileged-helper.",
            "Netzwerkseite zeigt danach 'WLAN-Verwaltung bereit' und unterstützte fremde WLANs erhalten den Button 'Verbinden'.",
            "Der Helper wird root:root unter /usr/local/libexec installiert und die sudoers-Datei mit visudo geprüft.",
            "Ein direkter Helper-Aufruf außerhalb von growstar.service wird durch den Cgroup-Guard abgelehnt.",
            "Ein simuliertes WLAN-Passwort erscheint in keinem Prozessargument.",
            "Ein simulierter Verifikationsfehler aktiviert weiterhin das vorherige WLAN als Rollback-Ziel.",
            "python3 check_phase4s31_network_helper.py läuft vollständig grün.",
            "/api/system/version meldet Version 3.7.4 und Build-Kennung 4S.3.1.",
        ),
    },
    {
        "version": "3.7.3",
        "date": "2026-08-17",
        "phase": "4S.3",
        "title": "Frischer WLAN-Scan und gezielte NetworkManager-Freigabe",
        "summary": (
            "Growstar erzwingt beim Öffnen und Aktualisieren der Netzwerkseite "
            "einen frischen WLAN-Scan. Die NetworkManager-Freigabe wird zugleich "
            "auf den Growstar-Systemdienst und benutzereigene WLAN-Profile begrenzt."
        ),
        "changes": (
            "Die Netzwerkseite erzwingt beim ersten Laden und über 'Aktualisieren' einen frischen WLAN-Scan mit --rescan yes.",
            "Normale interne Scans dürfen weiterhin den NetworkManager-Cache mit --rescan auto verwenden.",
            "WLAN-Ziellisten werden vor einem Verbindungsversuch nochmals mit einem frischen Scan geprüft.",
            "NetworkManager-Schreibbereitschaft akzeptiert jetzt settings.modify.own als bevorzugte, engere Alternative zu settings.modify.system.",
            "Neu angelegte WLAN-Verbindungen werden bei vorhandener modify-own-Berechtigung mit nmcli private yes dem Growstar-Dienstbenutzer zugeordnet.",
            "Die Netzwerkseite zeigt die einzelnen NetworkManager-Berechtigungszustände verständlicher an.",
            "Neue Polkit-Regel erlaubt nur growstar.service die Aktionen network-control, settings.modify.own und wifi.share.protected.",
            "Die Polkit-Regel wird zusätzlich an den tatsächlich in growstar.service konfigurierten Dienstbenutzer gebunden und enthält keinen fest codierten pi5-Benutzer.",
            "Ein idempotentes Installationsskript richtet die Regel einmalig unter /etc/polkit-1/rules.d ein; Flask und Gunicorn laufen weiterhin ohne Root-Rechte.",
            "Ein Entfernungsskript ermöglicht das saubere Zurücknehmen der NetworkManager-Freigabe.",
            "Der automatische Setup-Hotspot bleibt weiterhin deaktiviert und folgt erst nach bestätigtem grünem Schreibzugriff.",
        ),
        "tests": (
            "Netzwerkseite neu öffnen: sichtbare WLANs werden ohne vorherigen Terminal-Scan frisch ermittelt.",
            "Auf 'Aktualisieren' drücken: Backend verwendet --rescan yes statt --rescan auto.",
            "NetworkManager-Berechtigungsanzeige zeigt network-control, modify-own und modify-system getrennt an.",
            "Nach Installation der Polkit-Regel und Growstar-Neustart zeigt die Netzwerkseite 'WLAN-Verwaltung bereit'.",
            "Nicht verbundenes unterstütztes WLAN zeigt anschließend 'Verbinden' statt 'Nur lesen'.",
            "Neue WLAN-Verbindung wird bevorzugt als privates Benutzerprofil angelegt; settings.modify.system ist dafür nicht erforderlich.",
            "Polkit-Regel enthält keine pauschale Freigabe für den interaktiven Raspberry-Benutzer und keine modify-system-Berechtigung.",
            "python3 check_phase4s3_network_permissions.py läuft vollständig grün.",
            "/api/system/version meldet Version 3.7.3 und Build-Kennung 4S.3.",
        ),
    },
    {
        "version": "3.7.2",
        "date": "2026-08-17",
        "phase": "4S.2",
        "title": "WLAN-Wechsel direkt in Growstar mit sicherem Rückfall",
        "summary": (
            "Sichtbare WLAN-Netze können jetzt direkt über die Growstar-Oberfläche "
            "ausgewählt werden. Vor einem Wechsel merkt sich Growstar die aktive "
            "Verbindung und versucht bei einer fehlgeschlagenen Aktivierung "
            "automatisch zurückzuwechseln."
        ),
        "changes": (
            "Netzwerkseite kann sichtbare offene sowie WPA/WPA2/WPA3-Personal-WLANs direkt verbinden.",
            "Vor schreibenden Aktionen prüft Growstar die NetworkManager-Polkit-Berechtigungen seines laufenden Dienstkontos.",
            "WLAN-Schreibaktionen sind zusätzlich durch die bestehende settings.manage-Policy und CSRF-Schutz abgesichert.",
            "Das WLAN-Passwort wird nicht in Growstar-Konfigurationsdateien gespeichert und nicht als nmcli-Prozessargument übergeben.",
            "Geschützte WLAN-Secrets werden über die interaktive nmcli-Secret-Abfrage per stdin an NetworkManager übergeben.",
            "Vor dem Wechsel wird die aktive WLAN-Verbindung als Rückfallziel gespeichert.",
            "Das Ziel-WLAN gilt erst nach bestätigter Aktivierung und erhaltener IPv4-Adresse als erfolgreich.",
            "Bei Aktivierungs- oder Verifikationsfehler versucht Growstar automatisch die vorherige WLAN-Verbindung wiederherzustellen.",
            "WEP und Enterprise-WLAN 802.1X bleiben in dieser Ausbaustufe bewusst gesperrt.",
            "Gunicorn bindet Port 8001 nicht mehr an die feste IP 192.168.178.66, sondern netzwerkneutral an 0.0.0.0.",
            "Damit ist Growstar nicht mehr von der bisherigen Router-IP abhängig und für die kommende Setup-Hotspot-Erstinbetriebnahme vorbereitet.",
            "Der automatische Erstinbetriebnahme-Hotspot wird erst in der nächsten Stufe aktiviert, nachdem die NetworkManager-Schreibrechte auf dem Ziel-Raspberry bestätigt wurden.",
        ),
        "tests": (
            "Netzwerkseite zeigt unter 'Netzwerkverwaltung', ob NetworkManager-Schreibzugriff bereit ist.",
            "Bei fehlender NetworkManager-Freigabe bleiben alle WLAN-Verbinden-Schaltflächen deaktiviert.",
            "Bei vorhandener Freigabe zeigt ein nicht verbundenes WPA/WPA2/WPA3-Personal-WLAN eine Verbinden-Schaltfläche.",
            "WLAN-Passwort wird nur im Dialog eingegeben und nach dem Verbindungsversuch aus dem Formular gelöscht.",
            "Ein simuliertes geschütztes WLAN übergibt das Secret ausschließlich per stdin und niemals als Prozessargument.",
            "Bei simulierter fehlender IPv4-Verifikation wird die vorherige Verbindung als Rollback-Ziel aktiviert.",
            "python3 check_phase4s2_wifi_connect.py läuft vollständig grün.",
            "Nach dem Neustart lauscht Gunicorn weiterhin lokal auf 127.0.0.1:8000 und zusätzlich netzwerkneutral auf 0.0.0.0:8001.",
            "/api/system/version meldet Version 3.7.2 und Build-Kennung 4S.2.",
        ),
    },
    {
        "version": "3.7.1",
        "date": "2026-08-17",
        "phase": "4S.1",
        "title": "Netzwerk direkt im Grow Control erreichbar",
        "summary": (
            "Die in Phase 4S eingeführte Netzwerkdiagnose ist jetzt direkt im "
            "Grow-Control-Dashboard unter System & Infrastruktur erreichbar."
        ),
        "changes": (
            "Neue Netzwerk-Kachel im Grow-Control-Dashboard unter System & Infrastruktur.",
            "Die Kachel öffnet die bestehende Netzwerkseite über den registrierten Endpoint system_network_page.",
            "Die Netzwerk-Kachel ist nur mit der Berechtigung settings.view sichtbar.",
            "Das Layout und die mobile Darstellung verwenden die bestehende Modul-Kachelstruktur.",
            "Die Netzwerkdiagnose aus Phase 4S bleibt vollständig read-only und unverändert.",
            "Es werden weiterhin keine WLAN-Verbindungen, Hotspots oder NetworkManager-Profile verändert.",
        ),
        "tests": (
            "Grow Control öffnen: Unter System & Infrastruktur erscheint die Kachel 'Netzwerk'.",
            "Netzwerk-Kachel öffnen: /system/network muss ohne Umweg geladen werden.",
            "Die Kachel wird nur innerhalb des settings.view-Berechtigungsblocks gerendert.",
            "Status, Interfaces und WLAN-Scan auf der Netzwerkseite funktionieren weiterhin wie in Phase 4S.",
            "python3 check_phase4s1_network_dashboard.py läuft vollständig grün.",
            "/api/system/version meldet Version 3.7.1 und Build-Kennung 4S.1.",
        ),
    },
    {
        "version": "3.7.0",
        "date": "2026-08-17",
        "phase": "4S",
        "title": "Network Management – sichere Diagnosebasis",
        "summary": (
            "Growstar erhält ein eigenes Netzwerkmodul. Die erste Stufe zeigt "
            "NetworkManager-Status, aktive Interfaces, IP/Gateway/DNS und sichtbare "
            "WLAN-Netze an, ohne Netzwerkverbindungen zu verändern."
        ),
        "changes": (
            "Neue Systemseite /system/network für Netzwerkstatus und WLAN-Diagnose.",
            "Read-only NetworkManager-Integration über nmcli mit festen Argumentlisten und Timeout.",
            "Aktive LAN-/WLAN-Interfaces zeigen Verbindung, IPv4-Adressen, Gateway und DNS.",
            "WLAN-Scan zeigt SSID, Signalstärke, Sicherheit und aktuell verbundenes Netz.",
            "Doppelte SSIDs werden auf den stärksten sichtbaren Access Point zusammengefasst.",
            "Fehlender NetworkManager/nmcli wird als Diagnosezustand behandelt und erzeugt keinen Serverfehler.",
            "Netzwerkseite und APIs sind zusätzlich mit settings.view geschützt.",
            "System-Dashboard trennt Netzwerkverwaltung von Shelly-/Hardware-Verbindungen.",
            "Phase 4S bleibt vollständig read-only; Verbinden, Hotspot und Recovery verändern noch nichts.",
        ),
        "tests": (
            "Unter System erscheint die neue Karte 'Netzwerk' und öffnet /system/network.",
            "Auf dem Raspberry werden NetworkManager, Hostname und aktive Interfaces angezeigt.",
            "IP-Adresse, Gateway und DNS eines verbundenen Interfaces werden plausibel dargestellt.",
            "WLAN-Scan zeigt sichtbare SSIDs, Signalstärke und Sicherheitsart.",
            "Das aktuell verbundene WLAN wird im Scan markiert.",
            "Auf einem System ohne nmcli erscheint eine verständliche Diagnose statt eines HTTP-500-Fehlers.",
            "Die Seite bietet keine Buttons zum Verbinden, Trennen oder Starten eines Hotspots.",
            "python3 check_phase4s_network.py läuft vollständig grün.",
            "/api/system/version meldet Version 3.7.0 und Build-Kennung 4S.",
        ),
    },
    {
        "version": "3.6.6",
        "date": "2026-08-16",
        "phase": "4R.2",
        "title": "Doppelbelegung nennt Anforderer und Besitzer korrekt",
        "summary": (
            "Bei einer echten IP-/Relay-Doppelbelegung wird jetzt der tatsächlich "
            "bearbeitete Aktor als Anforderer und die bereits vorhandene Zuordnung "
            "als blockierender Besitzer gemeldet."
        ),
        "changes": (
            "Konfliktrichtung wird aus der tatsächlich geänderten Zuordnung statt aus der Geräte-Reihenfolge abgeleitet.",
            "Der bearbeitete Aktor wird immer als 'möchte ...' gemeldet.",
            "Der bereits belegende Aktor wird immer als bestehender Besitzer gemeldet.",
            "Die Geräte-Reihenfolge in DEVICE_HARDWARE beeinflusst die Fehlermeldung nicht mehr.",
            "Der bestehende globale IP/Relay-Doppelbelegungsschutz bleibt unverändert aktiv.",
        ),
        "tests": (
            "Entfeuchter besitzt einen Endpoint, Ventilator fordert ihn an: Ventilator muss als Anforderer erscheinen.",
            "Ventilator besitzt einen Endpoint, Entfeuchter fordert ihn an: Entfeuchter muss als Anforderer erscheinen.",
            "Identische unveränderte Zuordnung desselben Aktors bleibt konfliktfrei.",
            "Eine echte Doppelbelegung bleibt weiterhin atomar gesperrt.",
            "/api/system/version meldet Version 3.6.6 und Build-Kennung 4R.2.",
        ),
    },
    {
        "version": "3.6.5",
        "date": "2026-08-16",
        "phase": "4R.1",
        "title": "Hardware-Zuordnung ohne falsche Doppelbelegung",
        "summary": (
            "Die Verbindungsseite speichert nur noch tatsächlich geänderte "
            "Aktor-Zuordnungen. Unveränderte Geräte können dadurch keine "
            "scheinbaren Doppelbelegungen mehr auslösen."
        ),
        "changes": (
            "Verbindungen sendet beim Speichern nur noch geänderte Aktor-Zuordnungen an das Backend.",
            "Unveränderte IP-/Relay-Felder werden nicht mehr nebenbei normalisiert oder neu gespeichert.",
            "Eine unveränderte Zuordnung desselben Aktors bleibt ausdrücklich zulässig.",
            "Doppelbelegungsfehler nennen jetzt sowohl den bestehenden Besitzer als auch den kollidierenden Aktor.",
            "Der betroffene Aktor wird bei einem Konflikt auf der Verbindungsseite hervorgehoben.",
            "Der Schutz gegen echte Doppelbelegung von IP/Hostname + Relay bleibt vollständig aktiv.",
        ),
        "tests": (
            "Eine unveränderte bereits gespeicherte IP/Relay-Zuordnung erneut speichern: kein Konflikt.",
            "Ventilator eine neue IP mit leerem Relay zuweisen: Relay 0 wird nur für diesen geänderten Aktor übernommen.",
            "Ein anderer unveränderter Aktor mit unvollständiger IP-Zuordnung darf nicht automatisch Relay 0 erhalten.",
            "Zweiten Aktor absichtlich auf dieselbe IP + dasselbe Relay legen: echte Doppelbelegung muss weiter blockiert werden.",
            "Fehlermeldung muss bestehenden Besitzer und kollidierenden Aktor nennen.",
            "/api/system/version meldet Version 3.6.5 und Build-Kennung 4R.1.",
        ),
    },
    {
        "version": "3.6.4",
        "date": "2026-08-16",
        "phase": "4R",
        "title": "Bedienungssicherer Auto-Refresh",
        "summary": (
            "Automatische Live-Aktualisierungen überschreiben keine laufenden "
            "Benutzereingaben mehr. Sensor-Offsets lassen sich auf dem Handy "
            "ruhiger und zuverlässiger einstellen."
        ),
        "changes": (
            "Gerätesteuerung trennt Live-Status strikt von noch nicht gespeicherten Formularwerten.",
            "Modus, Zeit, Intervall und ENV-Auswahl werden durch den 3-Sekunden-Refresh nicht mehr zurückgesetzt.",
            "Sensor-Zuweisungen und Offsets werden durch den 10-Sekunden-Refresh nicht mehr überschrieben.",
            "Sensor-Livewerte und verfügbare Sensorquellen aktualisieren sich weiterhin automatisch.",
            "Offset-Tasten speichern mit kurzem Debounce statt mit einem POST pro Tastendruck.",
            "Offset-Speicherzugriffe werden pro Feld serialisiert, damit schnelle Eingaben nicht gegeneinander laufen.",
            "Refresh- und Speicherzugriffe erhalten einfache In-Flight-Guards gegen überlappende Requests.",
        ),
        "tests": (
            "Ventilator-Modus ändern und mindestens 5 Sekunden warten: Auswahl darf nicht zurückspringen.",
            "Zeit-, Intervall- oder ENV-Felder ändern und auf einen Auto-Refresh warten: Eingaben müssen erhalten bleiben.",
            "Temperatur- oder Feuchte-Sensor im Dropdown auswählen und länger als 10 Sekunden warten: Auswahl darf nicht zurückspringen.",
            "Sensor-Offset mehrfach schnell mit + oder − verstellen: sichtbarer Wert muss direkt folgen und anschließend stabil gespeichert werden.",
            "RAW-/Korrekturwerte und Hardware-/LIVE-Status müssen sich trotz aktiver Eingabe weiterhin automatisch aktualisieren.",
            "/api/system/version meldet Version 3.6.4 und Build-Kennung 4R.",
        ),
    },
    {
        "version": "3.6.3",
        "date": "2026-08-16",
        "phase": "4Q.1",
        "title": "Versionsanzeige ins Management Dashboard verschoben",
        "summary": (
            "Die Growstar-Version bleibt weiterhin direkt erreichbar, wird aber "
            "nicht mehr dauerhaft über jeder Seite eingeblendet."
        ),
        "changes": (
            "Globale schwebende Versionsanzeige aus base.html entfernt.",
            "Version dezent direkt bei 'Management Dashboard' platziert.",
            "NEU-Hinweis bleibt erhalten, bis die Patch-Information geöffnet wurde.",
            "Patch-Historie, Test-Checkliste und Versions-API bleiben unverändert erhalten.",
        ),
        "tests": (
            "Auf dem Management Dashboard steht dezent v3.6.3 neben der Überschrift.",
            "Auf Grow Control, Energie und anderen Unterseiten erscheint keine dauerhafte Versionsanzeige mehr.",
            "NEU erscheint auf dem Management Dashboard bei einer ungelesenen Version.",
            "Nach Öffnen der Patch-Information verschwindet NEU beim nächsten Dashboard-Aufruf.",
            "/api/system/version meldet Version 3.6.3 und Build-Kennung 4Q.1.",
        ),
    },
    {
        "version": "3.6.2",
        "date": "2026-08-16",
        "phase": "4Q",
        "title": "Versions- und Patch-Informationssystem",
        "summary": (
            "Growstar zeigt seine Version jetzt dezent in der Oberfläche und "
            "liefert zu jedem Update nachvollziehbare Änderungen und Testhinweise."
        ),
        "changes": (
            "Zentrale Release-Datei als einzige Quelle für die Growstar-Version.",
            "Dezenter Versions-Chip auf allen Seiten, die base.html verwenden.",
            "NEU-Hinweis pro Browser, bis die Patch-Information geöffnet wurde.",
            "Eigene Patch-Informationsseite mit Release-Historie.",
            "Persistente Test-Checkliste pro Version im Browser.",
            "Read-only API /api/system/version für Diagnose und Support.",
            "Backend-Startlog zeigt die tatsächlich laufende Growstar-Version.",
        ),
        "tests": (
            "Versions-Chip zeigt Growstar v3.6.2.",
            "NEU erscheint nach dem Update und verschwindet nach Öffnen der Patch-Information.",
            "Patch-Information zeigt die aktuelle Version und die Release-Historie.",
            "Test-Checkboxen bleiben nach einem Neuladen im selben Browser erhalten.",
            "/api/system/version meldet Version 3.6.2 und Build-Kennung 4Q.",
        ),
    },
    {
        "version": "3.6.1",
        "date": "2026-08-16",
        "phase": "4P",
        "title": "Frei benennbare Universal-Aktoren",
        "summary": (
            "Vier sichere Zusatzgeräte wurden eingeführt. Der erste Slot heißt "
            "standardmäßig Wasserpumpen und kann wie bestehende Aktoren gesteuert werden."
        ),
        "changes": (
            "Vier stabile Zusatzgeräte aux1 bis aux4.",
            "Frei wählbare Anzeigenamen pro Grow-Station.",
            "Dauerbetrieb, Zeitsteuerung, Intervall und ENV-Regelung.",
            "Integration in Dashboard, Verbindungen, Hardware, Watchdog und Energie.",
            "Bestehende SHADOW-, LIVE-, Safety- und Hardware-Guards bleiben aktiv.",
        ),
        "tests": (
            "Zusatzgerät im Design sichtbar schalten und frei benennen.",
            "IP/Hostname und Relay unter Verbindungen zuordnen.",
            "Intervallbetrieb prüfen.",
            "ENV mit Temperatur und/oder Luftfeuchtigkeit prüfen.",
            "Gerätenamen in Hardware, Watchdog und Energie kontrollieren.",
        ),
    },
)


def _display_date(value):
    try:
        return datetime.date.fromisoformat(str(value)).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return str(value or "")


def _copy_release(item):
    result = deepcopy(dict(item))
    result["changes"] = list(result.get("changes") or ())
    result["tests"] = list(result.get("tests") or ())
    result["date_label"] = _display_date(result.get("date"))
    return result


def current_release():
    return _copy_release(RELEASES[0])


def release_history():
    return [_copy_release(item) for item in RELEASES]


def release_summary():
    current = RELEASES[0]
    return {
        "version": current["version"],
        "release_date": current["date"],
        "phase": current["phase"],
        "title": current["title"],
    }


GROWSTAR_VERSION = RELEASES[0]["version"]
GROWSTAR_RELEASE_DATE = RELEASES[0]["date"]
GROWSTAR_INTERNAL_PHASE = RELEASES[0]["phase"]
