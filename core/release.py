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
