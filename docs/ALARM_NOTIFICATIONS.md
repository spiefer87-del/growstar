# Growstar Alarm & Notifications – 3.9.0

## Telegram-Erstinbetriebnahme

1. In Telegram `@BotFather` öffnen.
2. `/newbot` senden und Bot-Name/Username festlegen.
3. Den erzeugten Bot-Token in Growstar unter
   **Grow Control → Alarm & Benachrichtigungen** einfügen.
4. Den neuen Bot in Telegram öffnen und `/start` senden.
5. In Growstar **Chat finden** drücken.
6. **Testnachricht senden**.
7. Erst danach **Telegram aktiv** einschalten und Einstellungen speichern.

Der Bot-Token liegt ausschließlich in `instance/notifications.json`.
`instance/` ist seit Growstar 3.8 aus Git ausgeschlossen.

## Alarmquellen in 3.9.0

- Temperatursensor stale
- Feuchtesensor stale
- Temperatur unter `MIN_TEMP`
- Temperatur über `MAX_TEMP`
- Luftfeuchte über `MAX_HUM`
- optional Luftfeuchte unter `MIN_HUM`, falls dieser Schlüssel später verwendet wird
- Regelkreis stale
- Konfigurationsfehler
- Aktor nach mindestens zwei aufeinanderfolgenden Hardwarefehlern nicht erreichbar
- Safety-Supervisor stale
- Safety-Failsafe aktiv
- zentrale Growstar-Threads ausgefallen
- benötigter MQTT-Sensortraffic stale

## Zustandsmodell

Ein Alarm wird beim ersten Auftreten gemeldet und danach dedupliziert.
Optional sind Erinnerungen bei weiterhin aktiver Störung möglich.
Nach Behebung wird auf Wunsch eine Entwarnung versendet.

Nach Growstar-Neustart gilt 90 Sekunden Alarm-Startschutz.

## Grenzen

Telegram benötigt eine funktionierende Internetverbindung des Raspberry Pi.
`sendMessage` bestätigt, dass Telegram die Nachricht angenommen hat; Growstar
bezeichnet dies deshalb bewusst als „an Telegram übergeben“ und nicht als
garantierte Anzeige auf dem Telefon.
