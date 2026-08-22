#!/usr/bin/env python3
from __future__ import annotations

import hashlib
from pathlib import Path
import py_compile
import sys

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
OLD_RELEASE = CORE / "release.py"
RELEASES_DIR = CORE / "releases"
LEGACY = RELEASES_DIR / "legacy.py"
CURRENT = RELEASES_DIR / "current.py"
INIT = RELEASES_DIR / "__init__.py"
TEST = ROOT / "tests" / "regression" / "check_release_split.py"

EXPECTED_OLD_GIT_BLOB = "a9fba1a29da9a528e9d5562ee5f4ea9fb3f309f2"

CURRENT_CONTENT = '''# Growstar current release nodes.
#
# New patches are added here at the top. Once this file becomes large enough,
# an older group can be rolled into another history module without changing
# core.release's public API.

CURRENT_RELEASES = (
    {
        "version": "3.11.3",
        "date": "2026-08-22",
        "phase": "CORE.R1",
        "title": "Release-Historie aus core/release.py ausgelagert",
        "summary": (
            "Growstars inzwischen sehr große Release-Historie wird aus der "
            "öffentlichen core.release-Schnittstelle ausgelagert. Die bisherige "
            "Historie bleibt vollständig und unverändert erhalten, während neue "
            "Patch-Einträge künftig in kleinen, separat verwaltbaren Release-"
            "Modulen liegen. Runtime-, Hardware-, Sensor-, Netzwerk- und "
            "Spider-Farmer-Verhalten werden durch diesen Strukturpatch nicht "
            "verändert."
        ),
        "changes": (
            "Die bisherige vollständige core/release.py wird bytegleich als core/releases/legacy.py erhalten; kein historischer Release-Eintrag wird neu geschrieben, gekürzt oder gelöscht.",
            "core/releases/current.py enthält ab 3.11.3 ausschließlich neue Release-Nodes und bleibt dadurch für zukünftige mobile GitHub-Patches klein.",
            "core/releases/__init__.py setzt CURRENT_RELEASES und die unveränderte LEGACY_RELEASES-Historie zu genau einem RELEASES-Tupel zusammen.",
            "core/release.py bleibt die stabile öffentliche Schnittstelle mit RELEASES, current_release(), release_history(), release_summary(), GROWSTAR_VERSION, GROWSTAR_RELEASE_DATE und GROWSTAR_INTERNAL_PHASE.",
            "Bestehende Importe aus core.release sowie routes/release.py müssen dadurch nicht angepasst werden.",
            "Der direkte Vorgänger des Strukturpatches bleibt Growstar 3.11.2 / SF.2A; dessen vollständige Patch-Note liegt unverändert im Legacy-Modul.",
            "Der Patch verändert keine Growstar-Konfiguration, keine Sensorzuordnung, keine Shelly-Funktion, keinen MQTT-Pfad, keine Netzwerkgrenze und keine Spider-Farmer-Bridge.",
        ),
        "tests": (
            "check_release_split.py verlangt Growstar 3.11.3 / CORE.R1 als aktuellen Release und 3.11.2 / SF.2A unmittelbar darunter.",
            "Die Regression bestätigt, dass RELEASES exakt aus CURRENT_RELEASES plus LEGACY_RELEASES besteht und keine Versions-/Phasen-Duplikate enthält.",
            "Der vollständige Legacy-Bestand muss weiterhin 3.11.2 / SF.2A als ersten Eintrag besitzen.",
            "Die öffentliche core.release-API wird auf defensive Kopien, deutsches Datumslabel und unveränderte Summary-Felder geprüft.",
            "Die alte monolithische Historie wird bei der Migration vor jedem Schreibzugriff über ihren Git-Blob-SHA verifiziert.",
        ),
    },
)
'''

INIT_CONTENT = '''# Aggregated Growstar release history.
from .current import CURRENT_RELEASES
from .legacy import RELEASES as LEGACY_RELEASES

RELEASES = tuple(CURRENT_RELEASES) + tuple(LEGACY_RELEASES)

__all__ = (
    "CURRENT_RELEASES",
    "LEGACY_RELEASES",
    "RELEASES",
)
'''

WRAPPER_CONTENT = '''"""Zentrale Growstar-Release- und Patch-Informationen.

Die öffentliche Schnittstelle dieses Moduls bleibt stabil. Die eigentlichen
Release-Nodes liegen ab Growstar 3.11.3 unter ``core/releases``.
"""

from __future__ import annotations

from copy import deepcopy
import datetime

from .releases import RELEASES


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
'''

TEST_CONTENT = '''#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.release import (
    GROWSTAR_INTERNAL_PHASE,
    GROWSTAR_RELEASE_DATE,
    GROWSTAR_VERSION,
    RELEASES,
    current_release,
    release_history,
    release_summary,
)
from core.releases import CURRENT_RELEASES, LEGACY_RELEASES


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    require(
        GROWSTAR_VERSION == "3.11.3"
        and GROWSTAR_INTERNAL_PHASE == "CORE.R1",
        "Growstar meldet 3.11.3 / CORE.R1",
    )
    require(
        GROWSTAR_RELEASE_DATE == "2026-08-22",
        "Release-Datum bleibt zentral aus dem neuesten Node abgeleitet",
    )
    require(
        RELEASES == tuple(CURRENT_RELEASES) + tuple(LEGACY_RELEASES),
        "RELEASES setzt aktuelle und historische Module exakt zusammen",
    )
    require(
        RELEASES[1]["version"] == "3.11.2"
        and RELEASES[1]["phase"] == "SF.2A",
        "Direkter Vorgänger bleibt 3.11.2 / SF.2A",
    )
    require(
        LEGACY_RELEASES[0]["version"] == "3.11.2"
        and LEGACY_RELEASES[0]["phase"] == "SF.2A",
        "Legacy-Historie beginnt unverändert mit SF.2A",
    )

    identities = [(item.get("version"), item.get("phase")) for item in RELEASES]
    require(
        len(identities) == len(set(identities)),
        "Release-Historie enthält keine Versions-/Phasen-Duplikate",
    )

    current = current_release()
    require(
        current["version"] == "3.11.3"
        and current["date_label"] == "22.08.2026",
        "current_release liefert defensive Ansicht mit Datumslabel",
    )
    current["changes"].append("MUTATION")
    require(
        "MUTATION" not in RELEASES[0]["changes"],
        "current_release verändert internen Release-Node nicht",
    )

    history = release_history()
    history[0]["tests"].append("MUTATION")
    require(
        "MUTATION" not in RELEASES[0]["tests"],
        "release_history liefert defensive Kopien",
    )

    require(
        release_summary() == {
            "version": "3.11.3",
            "release_date": "2026-08-22",
            "phase": "CORE.R1",
            "title": "Release-Historie aus core/release.py ausgelagert",
        },
        "release_summary behält bestehende öffentliche Struktur",
    )

    require(
        (ROOT / "core" / "release.py").stat().st_size < 5000,
        "core/release.py ist nach dem Split wieder klein",
    )
    require(
        (ROOT / "core" / "releases" / "legacy.py").stat().st_size > 100000,
        "Vollständige historische Patch-Historie bleibt separat erhalten",
    )

    print("✅ Growstar Release-Split 3.11.3 / CORE.R1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
'''


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def fail(message):
    raise SystemExit(f"❌ {message}")


def main():
    if not OLD_RELEASE.exists():
        fail(f"Nicht gefunden: {OLD_RELEASE}")

    old_bytes = OLD_RELEASE.read_bytes()
    old_text = old_bytes.decode("utf-8")

    if '"version": "3.11.3"' in old_text and '"phase": "CORE.R1"' in old_text:
        print("✅ Release-Split scheint bereits installiert zu sein.")
        return

    if '"version": "3.11.2"' not in old_text or '"phase": "SF.2A"' not in old_text:
        fail("Ausgangsstand ist nicht Growstar 3.11.2 / SF.2A.")

    actual_blob = git_blob_sha(old_bytes)
    if actual_blob != EXPECTED_OLD_GIT_BLOB:
        fail(
            "core/release.py weicht vom verifizierten GitHub-main-Bestand ab.\n"
            f"Erwartet: {EXPECTED_OLD_GIT_BLOB}\n"
            f"Gefunden: {actual_blob}"
        )

    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    TEST.parent.mkdir(parents=True, exist_ok=True)

    LEGACY.write_bytes(old_bytes)
    CURRENT.write_text(CURRENT_CONTENT, encoding="utf-8")
    INIT.write_text(INIT_CONTENT, encoding="utf-8")
    OLD_RELEASE.write_text(WRAPPER_CONTENT, encoding="utf-8")
    TEST.write_text(TEST_CONTENT, encoding="utf-8")

    for path in (LEGACY, CURRENT, INIT, OLD_RELEASE, TEST):
        py_compile.compile(str(path), doraise=True)

    sys.path.insert(0, str(ROOT))
    from core.release import GROWSTAR_VERSION, GROWSTAR_INTERNAL_PHASE, RELEASES

    if GROWSTAR_VERSION != "3.11.3":
        fail(f"Unerwartete Version nach Migration: {GROWSTAR_VERSION}")
    if GROWSTAR_INTERNAL_PHASE != "CORE.R1":
        fail(f"Unerwartete Phase nach Migration: {GROWSTAR_INTERNAL_PHASE}")
    if RELEASES[1].get("version") != "3.11.2":
        fail("3.11.2 ist nach Migration nicht mehr direkter Vorgänger.")

    print("✅ core/releases/legacy.py: alte Historie bytegleich übernommen")
    print("✅ core/releases/current.py: 3.11.3 / CORE.R1 angelegt")
    print("✅ core/releases/__init__.py: Historie aggregiert")
    print("✅ core/release.py: kleine kompatible Schnittstelle")
    print("✅ tests/regression/check_release_split.py: Regression angelegt")
    print()
    print("Jetzt ausführen:")
    print("  /usr/bin/python3 tests/regression/check_release_split.py")


if __name__ == "__main__":
    main()
