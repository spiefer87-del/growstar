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
        "version": "3.10.1",
        "date": "2026-08-21",
        "phase": "4W.1",
        "title": "Hardware-Discovery-Regressionstest ohne Kommentar-False-Positive",
        "summary": (
            "Der Phase-4W-Regressionstest wertet den erklärenden Begriff "
            "'HardwareManager' in Docstrings nicht mehr fälschlich als "
            "produktiven Mutationspfad. Statt einer pauschalen Textsuche prüft "
            "der Test jetzt echte Python-Imports und Namensreferenzen."
        ),
        "changes": (
            "tests/regression/check_hardware_provisioning_discovery.py entfernt den fehlerhaften pauschalen Textcheck auf 'hardwaremanager'.",
            "Der Test parst core/hardware/shelly/provisioning.py nun per AST und prüft, dass core.hardware.manager nicht importiert wird.",
            "Zusätzlich wird geprüft, dass kein echter Python-Name HardwareManager im Discovery-Code referenziert wird.",
            "Die bestehenden Schutzprüfungen gegen Wifi.SetConfig, nmcli, manager.add, manager.save und shell=True bleiben erhalten.",
            "Erklärende Kommentare und Docstrings dürfen weiterhin ausdrücklich dokumentieren, dass der HardwareManager nicht beschrieben oder verändert wird.",
            "Die produktive Phase-4W-Bluetooth-Discovery bleibt byte-identisch und wird durch 4W.1 nicht verändert.",
            "Gateway-Scan, BTHome/BLE-Gateway-Scan, HardwareManager, Hardware-Inventar, Recovery, Netzwerk, Safety und Regelung bleiben unverändert.",
            "Es werden weiterhin keine WLAN-Zugangsdaten übertragen, keine Bluetooth-Geräte gepairt und keine Relais geschaltet.",
        ),
        "tests": (
            "Ausgangsbasis ist der aktuelle GitHub-main-Stand mit Growstar 3.10.0 / Phase 4W.",
            "core/release.py wurde vor der Patch-Erzeugung gegen GitHub-Blob-SHA d2136ae978f85a713d5175486a37087393c547a0 verifiziert.",
            "tests/regression/check_hardware_provisioning_discovery.py wurde gegen GitHub-Blob-SHA 9035d2331da2464ed050c93c56557325bfe35c24 verifiziert.",
            "Der fehlerhafte Literal-Check auf 'hardwaremanager' wurde entfernt.",
            "Ein erklärender Docstring mit dem Wort HardwareManager löst den Regressionstest nicht mehr aus.",
            "Ein echter Import von core.hardware.manager würde vom AST-basierten Test weiterhin erkannt und blockiert.",
            "Eine echte Referenz auf den Python-Namen HardwareManager würde weiterhin erkannt und blockiert.",
            "Die übrigen Mutationsschutzprüfungen aus Phase 4W bleiben unverändert aktiv.",
            "Die geänderten Python-Dateien wurden syntaktisch validiert.",
            "Die Release-Historie wurde geladen und bestätigt 3.10.1 / 4W.1 als neuen obersten Eintrag sowie 3.10.0 / 4W direkt darunter.",
        ),
    },
    {
        "version": "3.10.0",
        "date": "2026-08-21",
        "phase": "4W",
        "title": "Herstellerfreie Hardware-Erstinbetriebnahme – Discovery-Basis",
        "summary": (
            "Growstar kann nun über den lokalen Bluetooth-Adapter des Raspberry "
            "nach fabrikneuen Shelly-Geräten suchen, ohne die Shelly-App zu "
            "benötigen. Phase 4W bleibt absichtlich read-only: Es werden noch "
            "keine WLAN-Zugangsdaten übertragen, keine Geräte gepairt und keine "
            "Relais geschaltet."
        ),
        "changes": (
            "Vor der Implementierung wurden Gateway-Scan, Shelly-LAN-Discovery, BTHome/BLE-Gateway-Scan, HardwareManager, Recovery und Hardware-Oberfläche auf dem aktuellen GitHub-main geprüft.",
            "Der bestehende HardwareScanner und ShellyDiscovery bleiben unverändert für bereits im LAN erreichbare Shelly-Gateways zuständig.",
            "Der bestehende Shelly-Gateway-BTHome-Scan bleibt unverändert für BLU/BTHome-Sensoren zuständig und wird nicht für die Hersteller-App-freie Erstinbetriebnahme zweckentfremdet.",
            "Neue core/hardware/shelly/provisioning.py ergänzt ausschließlich die bisher fehlende lokale Raspberry-/BlueZ-Erkennung fabrikneuer Shellys.",
            "Der Discovery-Adapter verwendet bluetoothctl mit festen Argumentlisten ohne shell=True und validiert Bluetooth-Adressen vor Detailabfragen.",
            "Shelly-Kandidaten werden über den beworbenen Namen beziehungsweise die Shelly/Allterco ManufacturerData-Kennung 0x0BA9 erkannt.",
            "Ein passender Power-Strip-Gen4-Advertised-Name kann als unverbindlicher Modell-Hinweis S4PL-00416EU angezeigt werden; die endgültige Modellidentität bleibt nach der Provisionierung Aufgabe von Shelly.GetDeviceInfo und dem vorhandenen MODEL_NAMES-Katalog.",
            "Gefundene Erstinbetriebnahme-Kandidaten bleiben flüchtig und werden bewusst nicht in instance/hardware_inventory.json oder den HardwareManager geschrieben.",
            "Der vorhandene POST-Endpunkt /api/hardware/scan bleibt für den LAN-Gateway-Scan rückwärtskompatibel und unterstützt zusätzlich den expliziten Modus provisioning.",
            "Neue GET-Diagnose /api/hardware/provisioning/status zeigt, ob bluetoothctl und der lokale Raspberry-Bluetooth-Adapter für die Erkennung bereit sind.",
            "Die Hardware-Seite trennt jetzt sichtbar zwischen 'LAN-Gateway suchen' für bereits eingerichtete Shellys und 'Neue Shelly ohne Hersteller-App' für fabrikneue Geräte.",
            "Phase 4W verändert kein Raspberry-WLAN, überträgt kein WLAN-Passwort, führt kein Pairing/Trust/Connect aus, schaltet keine Shelly-Ausgänge und verändert keine Stations-Zuordnungen.",
            "Das bereits vorhandene Modell S4PL-00416EU für die Shelly Power Strip bleibt unverändert im bestehenden Shelly-Modellkatalog.",
            "Die vorhandene Hardware-Recovery bleibt unverändert und startet weiterhin keine versteckten Pairings unbekannter Geräte.",
            "Die eigentliche sichere WLAN-Provisionierung wird erst auf dieser getesteten Discovery-Basis in einem folgenden Schritt ergänzt.",
        ),
        "tests": (
            "Ausgangsbasis ist GitHub main Commit 260a6bce549a5845b5ff987553cd8a71cf24f624 mit Growstar 3.9.7 / Phase 4V.7.",
            "routes/hardware.py, templates/devices.html und core/release.py wurden vor der Patch-Erzeugung per Git-Blob-SHA gegen den aktuellen GitHub-main verifiziert.",
            "Der neue Discovery-Parser erkennt einen Shelly Power Strip Gen4 anhand eines Shelly-Advertised-Namens.",
            "Der neue Discovery-Parser erkennt einen Shelly auch ohne eindeutigen Namen anhand ManufacturerData Key 0x0BA9.",
            "Ein fremdes Bluetooth-Gerät ohne Shelly-Namen und ohne Shelly-ManufacturerData wird nicht als Provisioning-Kandidat ausgegeben.",
            "Der Regressionstest verwendet einen simulierten bluetoothctl-Runner und berührt damit weder den echten Raspberry-Bluetooth-Adapter noch reale Geräte.",
            "Der neue Discovery-Pfad enthält kein pair, trust, connect, Wifi.SetConfig, nmcli oder HardwareManager-Persistenz.",
            "Der bestehende /api/hardware/scan-Endpunkt und scanner.register(ShellyDiscovery()) bleiben weiterhin vorhanden.",
            "Der neue provisioning-Modus wird ausschließlich auf ausdrückliche Benutzeraktion gestartet und nicht in Hardware-Recovery oder Background-Threads eingebaut.",
            "Die vorhandene S4PL-00416EU-Modellkennung wird weiterhin im Shelly-Modellkatalog verlangt.",
            "Die geänderten Python-Dateien wurden syntaktisch validiert und der neue Regressionstest lokal mit simuliertem BlueZ-Output ausgeführt.",
            "Der Feature-Test prüft 3.10.0 / 4W als historischen RELEASES-Eintrag und bleibt dadurch bei späteren Growstar-Versionen wiederverwendbar.",
        ),
    },
    {
        "version": "3.9.7",
        "date": "2026-08-20",
        "phase": "4V.7",
        "title": "Safety-Supervisor-Regressionstest dauerhaft versionsunabhängig",
        "summary": (
            "Der Phase-4V.5-Regressionstest verlangt nicht mehr fälschlich, "
            "dass Growstar weiterhin exakt auf Version 3.9.5 / Phase 4V.5 "
            "laufen muss. Er schützt stattdessen dauerhaft die damals "
            "eingeführte Safety-Supervisor-Entkopplung und prüft den "
            "historischen Release-Eintrag."
        ),
        "changes": (
            "tests/regression/check_safety_supervisor_thread.py verlangt nicht mehr, dass GROWSTAR_VERSION aktuell 3.9.5 ist.",
            "Der Test verlangt nicht mehr, dass GROWSTAR_INTERNAL_PHASE aktuell 4V.5 ist.",
            "Stattdessen sucht der Checker in RELEASES nach dem historischen Feature-Release 3.9.5 / Phase 4V.5.",
            "Die eigentlichen Phase-4V.5-Funktionstests für den dedizierten Safety-Thread, das 2-Sekunden-Intervall, die fehlende direkte Shelly-Abhängigkeit, die Startreihenfolge und die Lock-Unabhängigkeit bleiben unverändert erhalten.",
            "Die produktive Safety-Stale-Grenze von 6 Sekunden wird weiterhin unverändert geprüft.",
            "Der Phase-4V.4-Shelly-RPC-Checker ist bereits seit 3.9.6 versionsunabhängig und bleibt unverändert.",
            "Repository-Baseline und Notifications verwenden bereits dynamische beziehungsweise historische Release-Prüfungen und benötigen keine Änderung.",
            "Damit sind die vier konsolidierten Regressionstests im aktuellen tests/regression-Verzeichnis von veralteten festen Aktuellversionsprüfungen bereinigt.",
            "Regelung, Safety-Laufzeitlogik, Shelly-RPC, Aktor-Health, Telegram, Netzwerk, UI und Restart-Policy werden durch Phase 4V.7 nicht verändert.",
            "Es werden keine Konfigurationswerte, Hardware-Zuordnungen oder Laufzeitdaten geändert.",
        ),
        "tests": (
            "Ausgangsbasis ist der aktuelle GitHub-main-Stand mit Growstar 3.9.6 / Phase 4V.6.",
            "core/release.py wurde vor der Patch-Erzeugung gegen GitHub-Blob-SHA ec050482489cdaa1b99257f22de87d91039394a9 verifiziert.",
            "tests/regression/check_safety_supervisor_thread.py wurde gegen GitHub-Blob-SHA 4a8da00b6ea5aa8906ec5652bbf4e5f8cfb85d5f verifiziert.",
            "Der feste Vergleich GROWSTAR_VERSION == 3.9.5 ist aus dem Phase-4V.5-Checker entfernt.",
            "Der feste Vergleich GROWSTAR_INTERNAL_PHASE == 4V.5 ist aus dem Phase-4V.5-Checker entfernt.",
            "Der historische RELEASES-Eintrag 3.9.5 / 4V.5 wird weiterhin explizit verlangt.",
            "Der Phase-4V.4-Shelly-RPC-Checker wurde im aktuellen GitHub-main kontrolliert und verwendet bereits die historische 3.9.4 / 4V.4-Prüfung.",
            "Die vier aktuellen Regressionstests wurden als Notifications, Repository-Baseline, Safety-Supervisor und Shelly-RPC identifiziert.",
            "Die erzeugten Python-Dateien wurden syntaktisch per ast.parse validiert.",
            "Die Release-Historie wurde geladen und bestätigt 3.9.7 / 4V.7 als neuen obersten Eintrag sowie 3.9.6 / 4V.6 direkt darunter.",
            "Der korrigierte Safety-Supervisor-Regressionstest wurde in einer isolierten Testumgebung erfolgreich ausgeführt.",
        ),
    },
    {
        "version": "3.9.6",
        "date": "2026-08-20",
        "phase": "4V.6",
        "title": "Shelly-RPC-Regressionstest von der aktuellen Version entkoppelt",
        "summary": (
            "Der Phase-4V.4-Regressionstest prüft nicht mehr fälschlich, dass "
            "Growstar weiterhin exakt auf Version 3.9.4 / Phase 4V.4 laufen "
            "muss. Stattdessen schützt er dauerhaft die damals eingeführte "
            "Shelly-RPC-Funktionalität und bestätigt den historischen Release-Eintrag."
        ),
        "changes": (
            "tests/regression/check_shelly_rpc_coordination.py verlangt nicht mehr, dass GROWSTAR_VERSION aktuell 3.9.4 ist.",
            "Der Test verlangt nicht mehr, dass GROWSTAR_INTERNAL_PHASE aktuell 4V.4 ist.",
            "Stattdessen sucht der Checker in RELEASES nach dem historischen Feature-Release 3.9.4 / Phase 4V.4.",
            "Die eigentlichen Phase-4V.4-Funktionstests für RLock, Shelly-RPC-Serialisierung, diagnostische Relay-Probe und Aktor-Health-Retry bleiben unverändert erhalten.",
            "Der Checker bleibt dadurch bei 3.9.6 und zukünftigen Growstar-Patches wiederverwendbar.",
            "Der Repository-Baseline-Test benötigt keine Änderung, weil er die aktuelle Version bereits dynamisch aus RELEASES[0] ableitet.",
            "Der Alarm-&-Notifications-Test benötigt keine Änderung, weil er ältere Feature-Releases bereits als historische RELEASES-Einträge prüft.",
            "Eine GitHub-Codeprüfung auf GROWSTAR_VERSION hat keinen weiteren historischen Regressionstest mit derselben 3.9.4-Fehlannahme ergeben.",
            "Regelung, Safety-Supervisor, Shelly-RPC-Laufzeitcode, Aktor-Health, Telegram, Netzwerk und Benutzeroberfläche werden durch Phase 4V.6 nicht verändert.",
            "Es werden keine Konfigurationswerte, Hardware-Zuordnungen oder Laufzeitdaten geändert.",
        ),
        "tests": (
            "Ausgangsbasis ist der aktuelle GitHub-main-Stand nach Growstar 3.9.5 / Phase 4V.5; letzter vor dem Build geprüfter Commit ist 005949f811d2af609694e03c882e0e04038f0e40.",
            "core/release.py wurde vor der Patch-Erzeugung gegen GitHub-Blob-SHA 5316d9e89db8990a01d4d988ea7484549c095c3e verifiziert.",
            "tests/regression/check_shelly_rpc_coordination.py wurde gegen GitHub-Blob-SHA 59dc30c50b89f05ce6145d0de690c00d97f88f01 verifiziert.",
            "Der feste Vergleich GROWSTAR_VERSION == 3.9.4 ist aus dem Phase-4V.4-Checker entfernt.",
            "Der feste Vergleich GROWSTAR_INTERNAL_PHASE == 4V.4 ist aus dem Phase-4V.4-Checker entfernt.",
            "Der historische RELEASES-Eintrag 3.9.4 / 4V.4 wird weiterhin explizit verlangt.",
            "Der Repository-Baseline-Test wurde geprüft und leitet Version und Phase bereits dynamisch vom obersten RELEASES-Eintrag ab.",
            "Der Notifications-Regressionstest wurde geprüft und verwendet für ältere Features bereits historische Release-Suchen.",
            "Die erzeugten Python-Dateien wurden syntaktisch per ast.parse validiert.",
            "Die Release-Historie wurde geladen und bestätigt 3.9.6 / 4V.6 als neuen obersten Eintrag sowie 3.9.5 / 4V.5 direkt darunter.",
            "Der neue historische 3.9.4-Release-Check wurde gegen die erzeugte 3.9.6-Release-Historie erfolgreich ausgeführt.",
        ),
    },
    {
        "version": "3.9.5",
        "date": "2026-08-20",
        "phase": "4V.5",
        "title": "Safety-Supervisor vom Shelly-Netzwerkthread entkoppelt",
        "summary": (
            "Der stationsbezogene Safety-Heartbeat läuft jetzt in einem eigenen "
            "Daemon-Thread. Langsame Shelly-, Energy- oder Relay-Failsafe-Zyklen "
            "können die reine Safety-Bewertung dadurch nicht mehr verzögern und "
            "keinen falschen 'Safety Supervisor Heartbeat stale'-Fehler erzeugen."
        ),
        "changes": (
            "Neue threads/safety.py führt den stationsübergreifenden Safety-Supervisor in einem eigenen growstar-safety Daemon-Thread aus.",
            "Das bisherige 2-Sekunden-Safety-Intervall bleibt unverändert bestehen.",
            "threads/shelly.py enthält ab 4V.5 keinen Safety-Zyklus und keinen äußeren Shelly-Lock mehr um run_all_live_safety.",
            "Der Shelly-Background bleibt ausschließlich für Relay-Sync-Failsafe, Energie-Polling, Verlauf und Tagesreset zuständig.",
            "Die normale Safety-Auswertung bleibt vollständig netzwerkfrei und liest weiterhin nur Runtime-State, Sensor-Freshness und den zentralen Aktor-Health-Cache.",
            "Ein Safety-Snapshot inklusive Heartbeat und Overrides wird weiterhin atomar gespeichert, bevor eine eventuell nötige reale Safe-Off-Aktion ausgeführt wird.",
            "Muss Safety einen Aktor wirklich AUS schalten, verwendet services.safety weiterhin set_device; der reale Shelly-Zugriff bleibt dadurch unter dem Transport-Lock aus Phase 4V.4.",
            "Der 3.9.4-Shelly-RPC-Lock und der Aktor-Health-Retry bleiben vollständig erhalten.",
            "Die bestehende Safety-Stale-Grenze von 6 Sekunden wird bewusst nicht erhöht; der Patch beseitigt die Blockierungsursache statt die Diagnose zu verstecken.",
            "app.py startet den neuen Safety-Supervisor unabhängig und vor dem Shelly-Background-Thread.",
            "Fehler einzelner Stationen bleiben wie bisher innerhalb run_all_live_safety isoliert und führen für die betroffene Runtime fail-closed zu Emergency-Safety.",
            "Restart-Policy, Regelung, Sensorgrenzen, Telegram, Netzwerkmanagement und Hardware-Zuordnungen werden durch Phase 4V.5 nicht verändert.",
            "Es werden keine neuen Konfigurationsschlüssel oder Migrationsdaten eingeführt.",
        ),
        "tests": (
            "Ausgangsbasis ist GitHub main Commit fb9bf81ac41198baa9773b7d2d05d01f45f22804 mit Growstar 3.9.4 / Phase 4V.4.",
            "app.py, core/release.py, core/context.py, threads/shelly.py und services/safety.py wurden vor der Patch-Erzeugung gegen ihre aktuellen GitHub-Blob-SHAs verifiziert.",
            "Der neue Safety-Thread enthält keinen Shelly-Lock, keine Requests- oder ShellyAPI-Abhängigkeit und delegiert ausschließlich an run_all_live_safety.",
            "Ein Safety-Zyklus kann im Regressionstest ausgeführt werden, während ein anderer Thread den Shelly-Transport-Lock hält.",
            "threads/shelly.py enthält weder run_all_live_safety noch SAFETY_INTERVAL und kann den Safety-Heartbeat damit nicht mehr durch Energy-/Relay-Polls verzögern.",
            "app.py startet growstar-safety mit safety_supervisor_loop und behält growstar-shelly separat bei.",
            "services/safety.py speichert den Snapshot weiterhin vor der physischen _enforce_snapshot-Aktion.",
            "Der produktive Safety-Stale-Schwellwert in core/safety.py bleibt unverändert bei 6 Sekunden.",
            "Der bestehende Phase-4V.4-Shelly-RPC-Regressionstest bleibt zusätzlich ausführbar.",
            "Notification- und Repository-Baseline-Regressionen bleiben zusätzlich ausführbar.",
            "core/release.py meldet Version 3.9.5 und Build-Kennung 4V.5.",
        ),
    },
    {
        "version": "3.9.4",
        "date": "2026-08-19",
        "phase": "4V.4",
        "title": "Shelly-RPC koordiniert und Aktor-Health gegen Einzelaussetzer gehärtet",
        "summary": (
            "Shelly-Inventar, BLE-RPC, Aktor-Schaltungen, Relay-Statusprüfungen "
            "und der bereits bestehende Energy/Failsafe-Zyklus teilen jetzt "
            "denselben reentranten Transport-Lock. Ein einzelner kurzzeitiger "
            "Relay-Read-Fehler löst außerdem nicht mehr sofort einen "
            "Safety-relevanten Offline-Eintrag aus."
        ),
        "changes": (
            "Der bestehende controllerweite shelly_lock wird von Lock auf RLock umgestellt, damit bereits geschützte Background-Zyklen sicher in geschützte Shelly-Helfer eintreten können.",
            "ShellyAPI.call serialisiert Inventar-, BLE- und weitere RPC-Aufrufe mit demselben Shelly-Transport-Lock.",
            "switch_shelly serialisiert Gen2-Schaltungen und den Gen1-Fallback mit demselben Transport-Lock.",
            "Die read-only Relay-Statusermittlung läuft ebenfalls unter dem Transport-Lock und kann damit nicht mehr gleichzeitig mit BLE-/Inventar-RPC oder regulären Relay-Schaltungen feuern.",
            "Der bestehende Energy- und Relay-Failsafe-Background war bereits durch ctx.shelly_lock geschützt und ist durch die gemeinsame Lock-Nutzung nun mit Hardware-, BLE- und Aktor-RPC koordiniert.",
            "Der Legacy-Helfer services.shelly.shelly_set verwendet ebenfalls den zentralen Transport-Lock.",
            "Neue probe_shelly_relay_state-Diagnostik unterscheidet unter anderem Timeout, Verbindungsfehler, HTTP-Status, ungültiges JSON, fehlendes output/ison und ungültige Relay-Bereiche.",
            "get_shelly_relay_state bleibt als rückwärtskompatibler bool/None-Wrapper erhalten.",
            "Der zentrale Aktor-Health-Poll wiederholt einen fehlgeschlagenen read-only Relay-Status nach 250 ms genau einmal.",
            "Erst wenn auch der zweite Versuch fehlschlägt, wird der Endpunkt als nicht erreichbar in den Safety-relevanten Health-Cache geschrieben.",
            "Ein beim zweiten Versuch wieder erreichbarer Shelly erzeugt keinen Offline-Health-Eintrag und damit keinen daraus resultierenden Safety-Failsafe.",
            "Bei einem echten zweifachen Ausfall bleibt die bestehende Safety-Reaktion unverändert aktiv.",
            "Der Health-Fehlertext enthält nach endgültigem Fehlschlag den konkreten Diagnosegrund statt nur 'Keine Antwort / ungültiger Relay-Status'.",
            "Der Aktor-Health-Poll bleibt vollständig read-only; der Retry sendet niemals Switch.Set oder Gen1-turn-Befehle.",
            "Regelung, Restart-Policy, Alarmgrenzen, Telegram-Deduplizierung und Benutzeroberfläche werden durch Phase 4V.4 nicht verändert.",
        ),
        "tests": (
            "Ausgangsbasis ist GitHub main Commit 1c38ff6367477e47421a3f0ab9cc66485fde4f54 mit Growstar 3.9.3 / Phase 4V.3.",
            "Der aktuelle core/release.py-Blob wurde vor der Patch-Erzeugung gegen SHA adaf2260f016c501cda335455ab5df0da651dac1 verifiziert.",
            "Der zentrale Shelly-Lock ist reentrant und kann im selben Thread verschachtelt betreten werden.",
            "Parallel gestartete kritische Abschnitte werden durch den gemeinsamen Shelly-Lock serialisiert.",
            "ShellyAPI.call, switch_shelly, Relay-Statusprobe und Legacy-shelly_set verwenden den gemeinsamen Transport-Lock.",
            "Ein simuliert fehlgeschlagener erster Aktor-Health-Read mit anschließend erfolgreichem zweiten Read bleibt erreichbar und erzeugt keinen Offline-Eintrag.",
            "Ein simuliert zweifach fehlgeschlagener Read bleibt offline und transportiert den konkreten Diagnosegrund.",
            "Die diagnostische Relay-Probe liefert bei einem gültigen Gen2-output einen booleschen Istzustand.",
            "Ein simulierter Timeout wird als Timeout-Diagnose statt als generischer ungültiger Relay-Status gemeldet.",
            "Der Aktor-Health-Code enthält weiterhin keinen Switch.Set- oder turn=-Schreibpfad.",
            "Bestehende Notification- und Repository-Baseline-Regressionen bleiben zusätzlich ausführbar.",
            "core/release.py meldet Version 3.9.4 und Build-Kennung 4V.4.",
        ),
    },
    {
        "version": "3.9.3",
        "date": "2026-08-19",
        "phase": "4V.3",
        "title": "Beleuchtungsdauer direkt aus Tag- und Nachtstart",
        "summary": (
            "Die Klima-&-Profile-Seite zeigt jetzt direkt unter Tag Start und "
            "Nacht Start die daraus resultierende Dauer der Tag- beziehungsweise "
            "Beleuchtungsphase an."
        ),
        "changes": (
            "Unter Tag Start und Nacht Start erscheint eine neue Anzeige 'Beleuchtungsdauer'.",
            "Die Beleuchtungsdauer wird ausschließlich aus DAY_START_MIN und NIGHT_START_MIN berechnet und benötigt keinen zusätzlichen Konfigurationswert.",
            "Bei Tag Start 06:00 und Nacht Start 23:00 zeigt Growstar automatisch 17 Stunden an.",
            "Zeitfenster über Mitternacht werden mit einem 24-Stunden-Modulo korrekt berechnet.",
            "Bei nicht vollen Stunden zeigt die Oberfläche zusätzlich die verbleibenden Minuten, zum Beispiel 17 Std. 30 Min.",
            "Die Anzeige aktualisiert sich bereits während einer Änderung der beiden Uhrzeitfelder und erneut nach dem Laden der Stationskonfiguration.",
            "Die bestehende Lichtsteuerung, DAY_START_MIN/NIGHT_START_MIN-Persistenz und Profilsteuerung bleiben unverändert.",
            "Es wird kein neuer persistenter Config-Schlüssel eingeführt; dadurch besteht kein Migrationsbedarf für bestehende Stationen.",
            "Alarm-Engine, Telegram, Hardware, Safety, Netzwerk und Restart-Policy werden durch diesen UI-Patch nicht verändert.",
        ),
        "tests": (
            "Aktuelle GitHub-main-Baselines von settings.html, release.py und check_notifications.py wurden vor dem Patch per Git-Blob-SHA verifiziert.",
            "Die Zeit-Kachel enthält die neue Beleuchtungsdauer-Anzeige.",
            "Die Berechnung verwendet (Nachtstart - Tagstart + 1440) modulo 1440 und unterstützt damit Tagphasen über Mitternacht.",
            "Änderungen an Tag Start oder Nacht Start aktualisieren die Anzeige unmittelbar.",
            "Volle Stunden werden als 'Stunden' dargestellt; Restminuten werden bei Bedarf zusätzlich angezeigt.",
            "Bestehende Klima-, Alarm- und Telegram-Regressionen bleiben im konsolidierten check_notifications.py erhalten.",
            "core/release.py meldet Version 3.9.3 und Build-Kennung 4V.3.",
        ),
    },
    {
        "version": "3.9.2",
        "date": "2026-08-19",
        "phase": "4V.2",
        "title": "Getrennte Regel- und Alarmtoleranzen pro Station",
        "summary": (
            "Sollwert-Regelung und Handy-Alarmierung besitzen jetzt bewusst "
            "unabhängige Toleranzen. Zusätzlich können die absoluten Temperatur- "
            "und Luftfeuchte-Grenzen pro Station direkt im Klima-Setup angepasst werden."
        ),
        "changes": (
            "Neue stationsbezogene TEMP_ALERT_TOL trennt die Temperatur-Benachrichtigung von DAY_TEMP_TOL/NIGHT_TEMP_TOL.",
            "Neue stationsbezogene HUM_ALERT_TOL trennt die Feuchte-Benachrichtigung von DAY_HUM_TOL/NIGHT_HUM_TOL.",
            "Bei 20 °C Soll und TEMP_ALERT_TOL=5 wird ein relativer Temperaturalarm ab 15 °C beziehungsweise 25 °C erzeugt, unabhängig von der engeren Regel-Toleranz.",
            "Relative Alarmgrenzen verwenden den aktuell wirksamen Live-Sollwert; eine laufende Temperaturrampe wird dadurch automatisch berücksichtigt.",
            "MIN_TEMP und MAX_TEMP bleiben absolute Temperatur-Schutzgrenzen und besitzen Alarmpriorität vor der relativen Abweichung.",
            "MIN_HUM wird als neue stationsbezogene untere Luftfeuchte-Alarmgrenze ergänzt; rückwärtskompatibler Default ist 0 Prozent.",
            "MAX_HUM bleibt die absolute obere Luftfeuchte-Alarmgrenze.",
            "Absolute Grenzverletzungen werden weiterhin als critical gemeldet; reine Sollwertabweichungen als error.",
            "Absolute und relative Sensoralarme verwenden denselben stabilen Alarm-Key, damit ein Grenzwechsel keine doppelten Recovery-/Neu-Alarm-Nachrichten erzeugt.",
            "Neue zentrale Validierung blockiert MIN_TEMP >= MAX_TEMP, ungültige Feuchtebereiche, nicht positive Alarmtoleranzen und negative Regel-Toleranzen atomar vor dem Config-Commit.",
            "Die stationsbezogene Klima-&-Profile-Seite zeigt Sollwert, Regel-Toleranz, Alarm-Toleranz und absolute Grenzen getrennt und mit berechneter Vorschau.",
            "Im Grow-Control-Setup erhält jede Station einen direkten Button 'Klima & Grenzwerte'.",
            "Die globale Benachrichtigungsregel heißt jetzt 'Sensorabweichung & Grenzwerte' und erklärt beide Alarmarten.",
            "Die Alarm-Toleranz selbst schaltet keine Aktoren und verändert die bestehende Regelungslogik nicht.",
            "Bestehende Telegram-Konfiguration, Bot-Token, Chat-ID, Wiederholungsintervall und Entwarnungslogik bleiben unverändert.",
        ),
        "tests": (
            "Aktuelle GitHub-Baselines von release.py, alerts.py, notifications.html, grow_control_setup.html und check_notifications.py wurden per Git-Blob-SHA verifiziert.",
            "20 °C Soll mit ±5 °C Alarmtoleranz erzeugt bei 24.9 °C noch keinen relativen Alarm.",
            "20 °C Soll mit ±5 °C Alarmtoleranz erzeugt ab 25.0 °C einen error-Alarm.",
            "60 Prozent Soll mit ±10 Prozent Alarmtoleranz erzeugt ab 70 Prozent einen error-Alarm.",
            "MAX_TEMP-Überschreitung bleibt critical und hat Priorität vor der relativen Sollwertabweichung.",
            "Ungültige MIN_TEMP/MAX_TEMP-Kombination wird durch die zentrale Grenzvalidierung blockiert.",
            "Setup enthält TEMP_ALERT_TOL, HUM_ALERT_TOL, MIN_HUM und MAX_HUM sowie erklärende Vorschauen.",
            "Grow-Control-Setup verlinkt jede Station direkt auf Klima & Grenzwerte.",
            "Config-Update ruft die Grenzvalidierung vor dem in-place Commit auf.",
            "python3 tests/regression/check_notifications.py läuft vollständig grün.",
            "tests/regression/check_repository_baseline.py bleibt als versionsunabhängiger Baseline-Test unverändert nutzbar.",
        ),
    },
    {
        "version": "3.9.1",
        "date": "2026-08-19",
        "phase": "4V.1",
        "title": "Regressionstests von der laufenden Versionsnummer entkoppelt",
        "summary": (
            "Die neue 3.9-Alarmfunktion war korrekt, aber zwei Regressionstests "
            "hatten die vorherige bzw. ursprüngliche Versionsnummer fest "
            "eingebaut. Die Tests prüfen jetzt dauerhaft gültige Invarianten "
            "statt bei jedem kommenden Patch erneut angepasst werden zu müssen."
        ),
        "changes": (
            "Der Repository-Baseline-Test erwartet nicht mehr fest Growstar 3.8.0 / Phase 4U.",
            "Der Repository-Baseline-Test prüft stattdessen, dass GROWSTAR_VERSION und GROWSTAR_INTERNAL_PHASE exakt dem obersten RELEASES-Eintrag folgen.",
            "Zusätzlich validiert der Baseline-Test die aktuelle Versionskennung als dreiteilige semantische Growstar-Version und verlangt eine nicht leere interne Phase.",
            "Die Abschlussmeldung des Baseline-Tests zeigt die tatsächlich aktuelle Growstar-Version und Phase dynamisch an.",
            "Der Alarm-&-Notifications-Test erwartet nicht mehr, dass 3.9.0 / 4V für immer die aktuelle Version bleibt.",
            "Der Alarm-&-Notifications-Test prüft stattdessen, dass der historische Feature-Release 3.9.0 / 4V weiterhin in RELEASES dokumentiert ist.",
            "Damit bleiben beide Regressionstests bei künftigen Patch- und Serienversionen wiederverwendbar.",
            "Alarm-Engine, Telegram-Versand, Regelung, Hardware, Restart-Policy, Netzwerk und Benutzeroberfläche werden durch 4V.1 nicht verändert.",
        ),
        "tests": (
            "Aktuelle GitHub-Versionen von core/release.py, check_repository_baseline.py und check_notifications.py wurden vor dem Patch per Git-Blob-SHA verifiziert.",
            "Der Repository-Baseline-Test enthält keine harte Anforderung mehr an 3.8.0 / 4U.",
            "Der Notification-Test enthält keine harte Anforderung mehr, dass 3.9.0 / 4V die aktuell laufende Version sein muss.",
            "Der Notification-Test bestätigt weiterhin, dass der Feature-Release 3.9.0 / 4V in den Patch Notes dokumentiert ist.",
            "core/release.py meldet Version 3.9.1 und Build-Kennung 4V.1.",
        ),
    },
    {
        "version": "3.9.0",
        "date": "2026-08-18",
        "phase": "4V",
        "title": "Zentrale Alarm-Engine und Telegram-Benachrichtigungen",
        "summary": (
            "Growstar kann kritische Sensor-, Regelkreis-, Hardware-, Safety- "
            "und Systemfehler jetzt zentral als Alarme verwalten und unabhängig "
            "vom geöffneten Browser per Telegram an ein Handy senden. "
            "Alarmüberwachung und Versand laufen getrennt von der Regelung."
        ),
        "changes": (
            "Neue zentrale Alarm-Engine verarbeitet ausschließlich den bestehenden read-only Watchdog-Health-Snapshot.",
            "Alarmüberwachung läuft in einem eigenen growstar-alerts Thread und führt keine Aktor- oder Shelly-Schreibzugriffe aus.",
            "Telegram-Versand läuft in einem getrennten growstar-notifications Queue-Worker und kann Watchdog oder Regelkreise nicht blockieren.",
            "Telegram-Nachrichten werden bei temporären Versandfehlern mit 5, 30 und 120 Sekunden Abstand automatisch erneut versucht.",
            "Neue Alarme werden dedupliziert; eine dauerhaft aktive Störung erzeugt nicht bei jedem 5-Sekunden-Zyklus eine neue Nachricht.",
            "Für weiterhin aktive Störungen kann ein Wiederholungsintervall von 15, 30, 60, 120 oder 240 Minuten gewählt oder vollständig deaktiviert werden.",
            "Bei Behebung einer zuvor gemeldeten Störung kann Growstar automatisch eine Entwarnung senden.",
            "Aktive Alarmzustände und eine begrenzte Alarmhistorie werden lokal unter instance/alarm_state.json persistiert.",
            "Nach jedem Growstar-Neustart gilt ein 90-Sekunden-Startschutz, damit anlaufende Sensor-/Threadzustände keine Fehlalarme erzeugen.",
            "Überwacht werden Sensor-Timeouts für Temperatur und Luftfeuchte.",
            "Kritische Temperaturwerte werden gegen die bestehende MIN_TEMP/MAX_TEMP-Konfiguration geprüft.",
            "Kritische Luftfeuchte wird gegen MAX_HUM und – falls später konfiguriert – MIN_HUM geprüft.",
            "Nicht erreichbare Aktoren werden nach mindestens zwei aufeinanderfolgenden Hardwarefehlern alarmiert.",
            "Safety-Supervisor-Stale und aktive stationsbezogene Safety-Failsafes erzeugen kritische Alarme.",
            "Stale Regelkreise und ungültige Stationskonfigurationen werden alarmiert.",
            "Ausgefallene zentrale Growstar-Threads sowie benötigter, stale MQTT-Sensortraffic können als Systemalarm gemeldet werden.",
            "Neue Seite /system/notifications zeigt Telegram-Einrichtung, Alarmregeln, aktive Alarme und Versandstatus.",
            "Neue Grow-Control-Dashboard-Kachel 'Alarm & Benachrichtigungen' führt direkt zur Benachrichtigungsseite.",
            "Telegram-Bot-Verbindung wird über den offiziellen Bot-Token geprüft; nach /start kann Growstar den privaten Chat automatisch über getUpdates finden.",
            "Eine Testnachricht kann direkt aus Growstar gesendet werden.",
            "Bot-Token und Chat-ID werden ausschließlich lokal in instance/notifications.json mit Dateimodus 0600 gespeichert und niemals in GitHub geschrieben.",
            "Der gespeicherte Bot-Token wird von der Growstar-API nie wieder an den Browser zurückgegeben.",
            "Telegram-Einstellungen sind mit settings.view lesbar und Änderungen/Testversand mit settings.manage geschützt; bestehender CSRF-Schutz bleibt aktiv.",
            "Telegram ist ein reiner Benachrichtigungskanal; die Funktion verändert weder Regelparameter noch Hardwarezustände.",
        ),
        "tests": (
            "Aktuelle GitHub-Baselines von app.py, core/release.py und grow_control_dashboard.html werden vor dem Patch per Git-Blob-SHA verifiziert.",
            "core/release.py meldet Version 3.9.0 und Build-Kennung 4V.",
            "Telegram-Client verwendet ausschließlich HTTPS über urllib und enthält keine shell=True-Ausführung.",
            "Telegram-Token wird syntaktisch validiert und weder geloggt noch als Prozessargument verwendet.",
            "Öffentliche Notification-Einstellungen enthalten kein bot_token-Feld.",
            "Lokale notification.json wird atomar geschrieben und auf Dateimodus 0600 gesetzt.",
            "Alarm-Engine importiert keine Aktor- oder Shelly-Schaltfunktionen.",
            "Ein simulierter stale Temperatursensor erzeugt genau einen stabilen Alarm-Key.",
            "Ein simulierter Temperaturwert über MAX_TEMP erzeugt einen critical sensor_limits Alarm.",
            "Ein simulierter Hardwarefehler unterhalb der Zwei-Fehler-Schwelle erzeugt noch keinen Alarm; ab zwei Fehlern wird alarmiert.",
            "app.py registriert Notification-Routen sowie getrennte Notification- und Alarm-Threads.",
            "Grow-Control-Dashboard enthält die neue Alarm-&-Benachrichtigungen-Kachel.",
            "Notification-Routen verlangen settings.view beziehungsweise settings.manage.",
            "python3 tests/regression/check_notifications.py läuft vollständig grün.",
            "Bestehender tests/regression/check_repository_baseline.py bleibt unverändert nutzbar.",
        ),
    },
    {
        "version": "3.8.0",
        "date": "2026-08-18",
        "phase": "4U",
        "title": "Bereinigte Repository- und Sicherheitsbaseline",
        "summary": (
            "Die lange 3.7-Patchserie wird mit einer bereinigten 3.8-Basis "
            "abgeschlossen. Historische Einmal- und Phasenartefakte werden aus "
            "dem aktiven Repository entfernt, Pico-Zugangsdaten werden nicht "
            "mehr versioniert und ein konsolidierter Repository-Baseline-Test "
            "ersetzt die große Sammlung einzelner Root-Checker."
        ),
        "changes": (
            "Start der neuen Growstar-3.8-Serie; die bestehende Regelungs-, Hardware-, Netzwerk- und Restart-Policy-Logik bleibt unverändert.",
            "53 historische check_*.py-Phasen- und Patchtests werden aus dem Repository-Root entfernt; ihr vollständiger Stand bleibt über die Git-Historie bis Commit 0e44d73639c0060eb7f520ccb7ef692081ce5ec6 nachvollziehbar.",
            "Neue konsolidierte Tests liegen ab 3.8 unter tests/regression statt als fortlaufende Patchdateien im Repository-Root.",
            "app_backup.py, das leere tools/test.py und das leere templates/admin/new.py werden als nicht verwendete Entwicklungsreste entfernt.",
            "Der veraltete Root-main.py-Pico-Prototyp wird entfernt; Growstar selbst startet weiterhin ausschließlich über Gunicorn mit app:flask_app.",
            "Die nicht mehr gerouteten Legacy-Templates heizung.html, abluft.html, licht.html und ventilator.html werden entfernt; Geräteansichten verwenden weiterhin das generische device_control.html.",
            "Die nicht mehr referenzierten Legacy-Templates tagebuch.html und pflanzendaten.html werden entfernt.",
            "Das nicht verwendete presets.py und die nicht referenzierte Root-style.css werden entfernt.",
            "Pico-WLAN-Zugangsdaten werden nicht mehr in pico_sensor_01/config.py oder pico_sensor_02/config.py versioniert.",
            "Für beide Pico-Sensorcontroller gibt es stattdessen config.example.py ohne reale Zugangsdaten; die lokale config.py wird per .gitignore ausgeschlossen.",
            ".gitignore nimmt zusätzlich lokale Growstar-Laufzeitdaten wie instance/, backups/, tent_configs/ und tests.json auf.",
            "profiles.json, core/profile.py und routes/profile.py bleiben ausdrücklich erhalten, weil sie im aktuellen Laufzeitpfad weiterhin aktiv verwendet werden.",
            "Die Phase-4T-Migrationswerkzeuge sowie Growstar-Service-, NetworkManager- und Netzwerk-Helper-Installer bleiben erhalten, damit bestehende Installations- und Upgradepfade nicht durch das Aufräumen beschädigt werden.",
            "Neue SECURITY.md dokumentiert verbindlich, dass WLAN-Passwörter, API-Tokens, Session-Secrets und andere produktive Zugangsdaten nicht in Git gespeichert werden dürfen.",
            "Ein zuvor versioniertes WLAN-Credential wird aus dem aktuellen Repository-Stand entfernt; da Git-Historie bereits veröffentlichte Secrets nicht zurücknimmt, muss das betroffene WLAN-Passwort kontrolliert rotiert werden.",
        ),
        "tests": (
            "core/release.py meldet Version 3.8.0 und Build-Kennung 4U.",
            "Im Repository-Root ist nach dem Cleanup kein check_*.py mehr versioniert.",
            "Alle gezielt entfernten Backup-, Prototyp-, Leer- und Legacy-Template-Dateien sind nicht mehr getrackt.",
            "pico_sensor_01/config.py und pico_sensor_02/config.py sind nicht mehr getrackt, ihre config.example.py-Dateien dagegen schon.",
            ".gitignore schützt Pico-Secrets sowie instance/, backups/, tent_configs/ und tests.json.",
            "Alle literalen render_template()-Ziele der aktiven Python-Routen werden gegen vorhandene Templates geprüft.",
            "Alle getrackten Python-Dateien werden syntaktisch per ast.parse geprüft, ohne Hardwarezugriffe auszuführen.",
            "app.py verwendet weiterhin apply_shutdown_restart_policy und registriert die aktive Profile- und Restart-Policy-Routenfamilie.",
            "core/profile.py, profiles.json und routes/profile.py bleiben Bestandteil der Baseline.",
            "install/activate_phase4t_without_old_shutdown.sh und tools/prepare_phase4t_restart.py bleiben für historische Upgradepfade erhalten.",
            "install/growstar.service.in startet weiterhin Gunicorn mit app:flask_app und Restart=always.",
            "services/network.py und install/growstar_network_helper.py bleiben ohne shell=True-Aufrufe.",
            "python3 tests/regression/check_repository_baseline.py läuft nach dem vollständigen GitHub-Cleanup grün.",
        ),
    },
    {
        "version": "3.7.10",
        "date": "2026-08-18",
        "phase": "4T.1",
        "title": "Phase-4T-Aktivierung und Setup-Einstieg korrigiert",
        "summary": (
            "Der einmalige Phase-4T-Migrationsweg kann das Vorbereitungsskript "
            "jetzt zuverlässig direkt aus dem tools-Verzeichnis starten. "
            "Zusätzlich ist das Neustart-Verhalten als sichtbare Unterkachel "
            "im Grow-Control-Setup erreichbar."
        ),
        "changes": (
            "tools/prepare_phase4t_restart.py ergänzt das Growstar-Projekt-Root vor allen core- und services-Imports selbst in sys.path.",
            "Der direkte Aufruf des Vorbereitungsskripts benötigt dadurch keinen manuellen PYTHONPATH-Workaround mehr.",
            "install/activate_phase4t_without_old_shutdown.sh übergibt zusätzlich explizit das erkannte PROJECT_DIR als PYTHONPATH.",
            "Die bestehende Fehlerbehandlung des Aktivierungsskripts bleibt erhalten: Bei einem Fehler wird der zuvor eingefrorene alte Growstar-Prozess mit SIGCONT fortgesetzt.",
            "Die Reihenfolge Freeze -> physische Restart-Policy -> alter Worker ohne historischen atexit-Shutdown beenden bleibt unverändert.",
            "Im Grow-Control-Setup erscheint eine neue Unterkachel 'Neustart-Verhalten'.",
            "Die Kachel führt auf die bereits vorhandene Seite /grow-control/setup/restart-policy.",
            "Die Beschreibung erklärt direkt, dass pro Station und Aktor zwischen Zustand beibehalten und sicher AUS gewählt wird.",
            "Die eigentliche Phase-4T-Restart-Policy, ihre sicheren Defaults und die Relay-Verifikation werden nicht verändert.",
            "Gunicorn, systemd-Service, Netzwerkmanagement und Caddy werden durch 4T.1 nicht verändert.",
        ),
        "tests": (
            "Projekt-Root-Bootstrap steht vor allen core-Imports im Vorbereitungsskript.",
            "Vorbereitungsskript verwendet Path(__file__).resolve().parents[1] als Projekt-Root.",
            "Aktivierungsskript setzt beim Aufruf zusätzlich PYTHONPATH auf das aus systemd erkannte PROJECT_DIR.",
            "SIGCONT-Fallback bei Fehlern bleibt im Aktivierungsskript vorhanden.",
            "SIGSTOP erfolgt weiterhin vor Policy-Vorbereitung und SIGKILL erst danach.",
            "Grow-Control-Setup enthält die sichtbare Kachel 'Neustart-Verhalten'.",
            "Die Setup-Kachel verlinkt über url_for('grow_control_restart_policy') auf die bestehende Restart-Policy-Seite.",
            "Die bestehende Restart-Policy-Seite und API bleiben unverändert registriert.",
            "python3 check_phase4t1_activation_setup.py läuft vollständig grün.",
            "/api/system/version meldet Version 3.7.10 und Build-Kennung 4T.1.",
        ),
    },
    {
        "version": "3.7.9",
        "date": "2026-08-18",
        "phase": "4T",
        "title": "Neustart-Verhalten pro Aktor konfigurierbar",
        "summary": (
            "Growstar schaltet bei einem geordneten Neustart nicht mehr pauschal "
            "alle Aktoren aus. Pro Station und Aktor kann gewählt werden, ob der "
            "physische Zustand unverändert bleiben oder das Relay sicher AUS "
            "geschaltet werden soll."
        ),
        "changes": (
            "Neue stationsbezogene RESTART_POLICY mit den ausschließlich erlaubten Aktionen KEEP und OFF.",
            "Beleuchtung und Licht 2 verwenden als sicheren Migrationsstandard KEEP; alle übrigen Aktoren starten mit OFF.",
            "KEEP sendet beim geordneten Growstar-/systemd-Shutdown ausdrücklich keinen Shelly-Schreibbefehl.",
            "OFF sendet unabhängig vom In-Memory-State einen realen AUS-Befehl und verifiziert den Relayzustand.",
            "shutdown_backend verwendet nicht mehr den historischen pauschalen set_device(..., False)-Not-Aus für alle Geräte.",
            "Während der Shutdown-Policy wird die Runtime auf disarming gesetzt, damit Regelkreis und Safety nicht gegen die Policy arbeiten.",
            "Beim Backend-Start werden vor allen Regel-/Failsafe-Threads die tatsächlichen Relayzustände synchronisiert.",
            "Die Start-Synchronisierung verwendet jetzt DEVICE_HARDWARE generisch und umfasst damit auch AUX1 bis AUX4.",
            "Neue Setup-Unterseite /grow-control/setup/restart-policy zeigt das Verhalten pro Station und Aktor.",
            "Änderungen an der Neustart-Policy werden sofort gespeichert und gelten bereits für den nächsten geordneten Neustart; ein weiterer Neustart zum Speichern ist nicht nötig.",
            "Neue stationsbezogene API /api/tents/<tent_id>/restart-policy verwendet die bestehende Grow-Konfigurationsberechtigung.",
            "Ein erzwungenes automatisches EIN beim Neustart wird aus Sicherheitsgründen bewusst nicht angeboten.",
            "Die Policy gilt für geordnete Prozess-/systemd-Neustarts und Shutdowns; ein abrupter Stromausfall kann softwareseitig keinen letzten Schaltbefehl ausführen.",
            "Ein einmaliges Phase-4T-Aktivierungsskript verhindert beim Wechsel von 3.7.8, dass der alte pauschale Alles-AUS-aexit-Handler noch einmal das Licht unterbricht.",
            "Das Aktivierungsskript friert den alten Growstar-Prozess zuerst per SIGSTOP ein, wendet die neue physische Policy an und beendet erst danach den alten Worker ohne dessen historischen Shutdown-Handler.",
            "Gunicorn-Bindings, Caddy, Netzwerkmanagement und die bestehende Safety-Supervisor-Logik bleiben unverändert.",
        ),
        "tests": (
            "Default-Policy meldet light/light2=KEEP und heating=OFF.",
            "Ungültige Geräte-IDs und andere Aktionen als KEEP/OFF werden atomar abgelehnt.",
            "KEEP erzeugt im simulierten Shutdown keinen Shelly-Schreibzugriff.",
            "OFF erzeugt einen realen AUS-Befehl auch dann, wenn der Runtime-State bereits fälschlich False meldet.",
            "OFF wird nach dem Schreiben direkt am Relay verifiziert und aktualisiert erst danach den Runtime-State.",
            "Start-Synchronisierung basiert auf DEVICE_HARDWARE und umfasst AUX-Aktoren.",
            "app.shutdown_backend enthält keinen pauschalen set_device(device, False)-Loop mehr.",
            "Setup-API und Setup-Unterseite für Neustart-Verhalten sind registriert.",
            "Das einmalige Aktivierungsskript enthält SIGSTOP vor Policy-Vorbereitung und SIGKILL erst danach.",
            "python3 check_phase4t_restart_policy.py läuft vollständig grün.",
            "/api/system/version meldet Version 3.7.9 und Build-Kennung 4T.",
        ),
    },
    {
        "version": "3.7.8",
        "date": "2026-08-17",
        "phase": "4S.3.5",
        "title": "Abgeleiteten WLAN-PSK nicht mehr als Originalpasswort anzeigen",
        "summary": (
            "Growstar unterscheidet jetzt zuverlässig zwischen einer gespeicherten "
            "WLAN-Passphrase und einem bereits abgeleiteten 64-stelligen WPA-PSK. "
            "Ein abgeleiteter Schlüssel wird nicht mehr irreführend als Passwort "
            "angezeigt und nicht an den Browser übertragen."
        ),
        "changes": (
            "Der Netzwerk-Helper klassifiziert gespeicherte WPA-Credentials als Passphrase oder 64-stelligen Hex-PSK.",
            "Ein 64-stelliger Hex-PSK wird als derived_psk erkannt.",
            "Bei derived_psk gibt der Helper ausschließlich Metadaten zurück und niemals den vollständigen WLAN-Schlüssel.",
            "Die Growstar-API überträgt den abgeleiteten PSK deshalb nicht an den Browser.",
            "Die Netzwerkseite zeigt bei derived_psk klar 'Originalpasswort nicht auslesbar' statt eines falschen Passworts.",
            "Nur wenn NetworkManager tatsächlich eine Passphrase speichert, kann 'Passwort anzeigen' weiterhin den Klartext kurz einblenden.",
            "Die automatische 15-Sekunden-Maskierung für rücklesbare Passphrasen bleibt erhalten.",
            "Passwort ändern, WLAN-Wechsel, Scan, Rollback und der privilegierte Netzwerk-Helper bleiben ansonsten unverändert.",
            "Die SSID-Prüfung der get_password-Aktion behandelt Steuerzeichen wieder korrekt statt nach literalen Escape-Strings zu suchen.",
            "Growstar liest Netplan nicht zusätzlich nach Klartext-Secrets aus; auf dem getesteten Raspberry enthält Netplan ebenfalls nur denselben abgeleiteten 64-Hex-PSK.",
            "Gunicorn-, systemd- und Caddy-Konfigurationen werden durch diesen Patch nicht verändert.",
            "Der Netzwerk-Helper muss nach git pull erneut mit dem bestehenden Installer nach /usr/local/libexec kopiert werden.",
        ),
        "tests": (
            "Ein simuliertes 64-stelliges Hex-Credential wird als derived_psk erkannt.",
            "Bei derived_psk enthält die Helper-Antwort kein password-Feld.",
            "Der Webservice gibt derived_psk-Metadaten weiter, ohne ein Secret zu verlangen.",
            "Die Netzwerkseite zeigt für derived_psk 'Originalpasswort nicht auslesbar'.",
            "Eine normale simulierte Passphrase bleibt revealable und kann weiterhin angezeigt werden.",
            "Eine Passphrase wird nach 15 Sekunden weiterhin automatisch maskiert.",
            "Nicht aktive SSIDs und nicht unterstützte WLAN-Sicherheitsarten bleiben für die Credential-Abfrage gesperrt.",
            "python3 check_phase4s35_wifi_credential_type.py läuft vollständig grün.",
            "/api/system/version meldet Version 3.7.8 und Build-Kennung 4S.3.5.",
        ),
    },
    {
        "version": "3.7.7",
        "date": "2026-08-17",
        "phase": "4S.3.4",
        "title": "WLAN-Passwort anzeigen und Growstar-Systemdienst reproduzierbar installieren",
        "summary": (
            "Das gespeicherte Passwort der aktuell verbundenen Personal-WLAN-"
            "Verbindung kann jetzt auf ausdrückliche Administrator-Aktion kurz "
            "angezeigt werden. Zusätzlich erhält Growstar einen reproduzierbaren "
            "systemd-Installer für den bestehenden Gunicorn-Betrieb."
        ),
        "changes": (
            "Die verbundene WPA/WPA2/WPA3-Personal-Verbindung zeigt das Passwort standardmäßig nur maskiert.",
            "Ein expliziter Button 'Passwort anzeigen' lädt das Secret nur mit settings.manage und bestehendem CSRF-Schutz.",
            "Die Secret-Antwort trägt Cache-Control no-store, Pragma no-cache und Expires 0.",
            "Das eingeblendete WLAN-Passwort wird nach 15 Sekunden automatisch wieder maskiert und kann vorher manuell verborgen werden.",
            "Der root-eigene Netzwerk-Helper erhält die eng definierte Aktion get_password.",
            "Der Helper gibt nur das Passwort der tatsächlich aktuell verbundenen Personal-WLAN-Verbindung frei.",
            "WEP, Enterprise-WLAN und nicht aktive SSIDs können über diese Aktion kein Secret auslesen.",
            "Das WLAN-Passwort wird weiterhin nicht in Growstar-Dateien gespeichert und erscheint nicht in Prozessargumenten.",
            "Neue growstar.service-Vorlage bildet den bestehenden Gunicorn-Systemdienst reproduzierbar ab.",
            "Der Service-Installer ermittelt Growstar-Verzeichnis, Dienstbenutzer, Gruppe und Gunicorn-Binary dynamisch statt pi5 oder /home/pi5 fest zu codieren.",
            "Growstar wird weiterhin ausdrücklich nicht als root gestartet.",
            "Der Installer aktiviert growstar.service für den Systemstart, startet ihn standardmäßig aber nicht ungefragt neu.",
            "Mit --start kann der Installer bei einer Factory-/Neuinstallation den Dienst direkt starten.",
            "Vorhandene systemd-Drop-ins wie GROWSTAR_HTTPS_ONLY bleiben unangetastet.",
            "Die bestehende gunicorn.conf.py bleibt unverändert: 127.0.0.1:8000 für Caddy und 0.0.0.0:8001 für lokale/Setup-Erreichbarkeit.",
            "Caddy/DuckDNS bleiben bewusst außerhalb dieses Installers und werden in einem separaten Infrastruktur-Schritt behandelt.",
        ),
        "tests": (
            "Beim verbundenen Personal-WLAN erscheint 'Passwort anzeigen' neben 'Passwort ändern'.",
            "Ohne bewusste Aktion bleibt das Passwort ausschließlich maskiert.",
            "Die Passwortanzeige verwendet POST, settings.manage, CSRF und no-store-Header.",
            "Nach 15 Sekunden wird ein eingeblendetes Passwort wieder maskiert.",
            "Der Helper verweigert get_password für eine andere als die aktuell verbundene SSID.",
            "Der Helper verweigert die Passwortanzeige für nicht unterstützte Sicherheitsarten.",
            "growstar.service.in enthält network-online-Abhängigkeit, Restart=always und app:flask_app.",
            "Der Service-Installer enthält keinen fest codierten Benutzer pi5 und keinen fest codierten Pfad /home/pi5/growstar.",
            "Der Service-Installer lehnt root als Growstar-Dienstbenutzer ab und erhält bestehende Drop-ins.",
            "python3 check_phase4s34_password_service.py läuft vollständig grün.",
            "/api/system/version meldet Version 3.7.7 und Build-Kennung 4S.3.4.",
        ),
    },
    {
        "version": "3.7.6",
        "date": "2026-08-17",
        "phase": "4S.3.3",
        "title": "Passwort der bestehenden WLAN-Verbindung sicher ändern",
        "summary": (
            "Das Passwort der aktuell verbundenen WPA/WPA2/WPA3-Personal-"
            "Verbindung kann jetzt direkt in Growstar geändert werden. "
            "Growstar hält das bisherige Secret ausschließlich im privilegierten "
            "Netzwerk-Helper als Rollback-Sicherung und bestätigt die neue "
            "Verbindung erst nach erfolgreicher IPv4-Aktivierung."
        ),
        "changes": (
            "Das aktuell verbundene geschützte WLAN erhält auf der Netzwerkseite die Aktion 'Passwort ändern'.",
            "Das neue Passwort muss zur Vermeidung von Tippfehlern zweimal eingegeben werden.",
            "Die Passwortänderung ist wie andere Netzwerkmutationen durch settings.manage und CSRF geschützt.",
            "Das bisherige PSK wird ausschließlich im root-eigenen Netzwerk-Helper mit --show-secrets gelesen und niemals an Flask oder den Browser zurückgegeben.",
            "Das neue PSK wird über den interaktiven nmcli-Verbindungseditor per stdin gespeichert und erscheint nicht in der Prozessargumentliste.",
            "Nach dem Speichern wird das bestehende NetworkManager-Profil explizit neu aktiviert.",
            "Die Passwortänderung gilt erst als erfolgreich, wenn dieselbe SSID wieder aktiv ist und eine IPv4-Adresse vorliegt.",
            "Bei Aktivierungs- oder Verifikationsfehler schreibt der Helper automatisch das vorherige PSK zurück und aktiviert die bisherige Verbindung erneut.",
            "WEP und Enterprise-WLAN bleiben für diese Funktion bewusst ausgeschlossen; unterstützt werden WPA/WPA2/WPA3-Personal-Profile.",
            "WLAN-Scan, Gunicorn-Binding und Setup-Hotspot-Status bleiben unverändert.",
            "Der Netzwerk-Helper muss nach git pull erneut mit dem bestehenden Installer nach /usr/local/libexec kopiert werden.",
        ),
        "tests": (
            "Beim aktuell verbundenen WPA/WPA2/WPA3-Personal-WLAN erscheint 'Passwort ändern'.",
            "Offene, WEP- und Enterprise-Netze erhalten keine Passwortänderungsaktion.",
            "Zwei abweichende neue Passwörter werden bereits im Browser blockiert.",
            "Der Webservice delegiert die Passwortänderung ausschließlich an die Helper-Aktion update_password.",
            "Weder altes noch neues WLAN-Passwort erscheint in nmcli-Prozessargumenten.",
            "Der Helper liest das alte PSK nur intern als Rollback-Sicherung.",
            "Nach erfolgreicher Änderung wird das bestehende Profil neu aktiviert und auf SSID + IPv4 geprüft.",
            "Ein simulierter Fehler stellt das alte PSK wieder her und aktiviert die vorherige Verbindung erneut.",
            "python3 check_phase4s33_wifi_password.py läuft vollständig grün.",
            "/api/system/version meldet Version 3.7.6 und Build-Kennung 4S.3.3.",
        ),
    },
    {
        "version": "3.7.5",
        "date": "2026-08-17",
        "phase": "4S.3.2",
        "title": "WLAN-Scan nutzt den privilegierten Netzwerk-Helper",
        "summary": (
            "Der echte WLAN-Neuscan wird jetzt über denselben eng begrenzten "
            "Netzwerk-Helper angefordert wie andere privilegierte "
            "NetworkManager-Aktionen. Die fertige Access-Point-Liste wird danach "
            "weiterhin unprivilegiert vom Growstar-Webprozess gelesen."
        ),
        "changes": (
            "Fehler 'org.freedesktop.NetworkManager.wifi.scan request failed: not authorized' im Webprozess behoben.",
            "Der Force-Scan ruft NetworkManager nicht mehr direkt aus Gunicorn auf.",
            "Der root-eigene Growstar-Netzwerk-Helper erhält die neue fest definierte Aktion 'scan'.",
            "Die Helper-Aktion fordert ausschließlich einen frischen Scan auf dem erkannten WLAN-Interface an und verändert keine Verbindung.",
            "Nach erfolgreicher Scan-Anforderung wartet Growstar weiterhin fünf Sekunden auf NetworkManager und den WLAN-Treiber.",
            "Die fertige Access-Point-Liste wird anschließend mit --rescan no ohne zusätzliche privilegierte Aktion gelesen.",
            "Der normale Cache-/Listenabruf bleibt unprivilegiert.",
            "WLAN-Verbindung, Passwortbehandlung, Rollback, Gunicorn-Binding und Authentifizierung bleiben unverändert.",
            "Der bereits installierte Helper muss nach git pull einmalig mit dem bestehenden Installer aktualisiert werden.",
        ),
        "tests": (
            "Direkter API-Aufruf /api/config/network/wifi?refresh=1 darf keinen 'not authorized'-Fehler mehr liefern.",
            "Ein erzwungener Scan wird im Service ausschließlich über die Helper-Aktion 'scan' angefordert.",
            "Der unprivilegierte Service führt bei force=True keinen direkten 'nmcli device wifi rescan'-Aufruf mehr aus.",
            "Nach der Helper-Antwort wartet Growstar die definierte Settle-Zeit ab.",
            "Die abschließende WLAN-Liste wird mit --rescan no gelesen.",
            "Der Helper unterstützt ausschließlich die neue explizite Aktion 'scan' zusätzlich zu probe und connect.",
            "Die Helper-Scan-Aktion verändert keine aktive Verbindung und legt kein NetworkManager-Profil an.",
            "python3 check_phase4s32_privileged_scan.py läuft vollständig grün.",
            "/api/system/version meldet Version 3.7.5 und Build-Kennung 4S.3.2.",
        ),
    },
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
