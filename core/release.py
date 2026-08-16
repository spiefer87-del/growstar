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
