#!/usr/bin/env python3
"""Regression for Growstar release-history split.

This test is intentionally version-agnostic for the current release. It verifies
that core.release derives its public version/phase/date/title from the first
entry of the split release history, while preserving the historical chain.

That makes the regression survive future releases such as SF.3, SF.4, etc.
without hard-coding the then-current version into this infrastructure test.
"""

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

from core.releases import (
    CURRENT_RELEASES,
    LEGACY_RELEASES,
)


def require(condition, message):

    if not condition:
        raise AssertionError(message)

    print("✅", message)


def main():

    require(
        len(RELEASES) >= 2,
        "Release-Historie enthält aktuellen Release und Vorgänger",
    )

    require(
        len(CURRENT_RELEASES) >= 1,
        "Aktuelles Release-Modul enthält mindestens einen Release",
    )

    newest = RELEASES[0]

    require(
        GROWSTAR_VERSION == newest["version"],
        "GROWSTAR_VERSION folgt dynamisch dem obersten RELEASES-Eintrag",
    )

    require(
        GROWSTAR_INTERNAL_PHASE == newest["phase"],
        "GROWSTAR_INTERNAL_PHASE folgt dynamisch dem obersten RELEASES-Eintrag",
    )

    require(
        GROWSTAR_RELEASE_DATE == newest["date"],
        "GROWSTAR_RELEASE_DATE folgt dynamisch dem obersten RELEASES-Eintrag",
    )

    require(
        RELEASES == tuple(CURRENT_RELEASES) + tuple(LEGACY_RELEASES),
        "RELEASES setzt aktuelle und historische Module exakt zusammen",
    )

    require(
        RELEASES[len(CURRENT_RELEASES)] == LEGACY_RELEASES[0],
        "Übergang von aktueller zu historischer Release-Datei bleibt lückenlos",
    )

    require(
        LEGACY_RELEASES[0]["version"] == "3.11.2"
        and LEGACY_RELEASES[0]["phase"] == "SF.2A",
        "Legacy-Historie beginnt unverändert mit 3.11.2 / SF.2A",
    )

    require(
        RELEASES[-1]["version"] == LEGACY_RELEASES[-1]["version"]
        and RELEASES[-1]["phase"] == LEGACY_RELEASES[-1]["phase"],
        "Historisches Ende der Release-Historie bleibt erhalten",
    )

    identities = [
        (
            item.get("version"),
            item.get("phase"),
        )
        for item in RELEASES
    ]

    require(
        len(identities) == len(set(identities)),
        "Release-Historie enthält keine Versions-/Phasen-Duplikate",
    )

    current = current_release()

    require(
        current["version"] == newest["version"]
        and current["phase"] == newest["phase"],
        "current_release liefert den aktuell obersten Release",
    )

    require(
        current["date_label"] == "22.08.2026",
        "current_release liefert weiterhin das deutsche Datumslabel",
    )

    current["changes"].append("MUTATION")

    require(
        "MUTATION" not in RELEASES[0]["changes"],
        "current_release verändert den internen Release-Node nicht",
    )

    history = release_history()

    require(
        len(history) == len(RELEASES),
        "release_history liefert die vollständige kombinierte Historie",
    )

    history[0]["tests"].append("MUTATION")

    require(
        "MUTATION" not in RELEASES[0]["tests"],
        "release_history liefert defensive Kopien",
    )

    summary = release_summary()

    require(
        summary == {
            "version": newest["version"],
            "release_date": newest["date"],
            "phase": newest["phase"],
            "title": newest["title"],
        },
        "release_summary wird dynamisch aus dem aktuellen Release erzeugt",
    )

    wrapper = ROOT / "core" / "release.py"
    legacy = ROOT / "core" / "releases" / "legacy.py"
    current_file = ROOT / "core" / "releases" / "current.py"

    require(
        wrapper.is_file(),
        "core/release.py existiert als öffentliche Release-Schnittstelle",
    )

    require(
        legacy.is_file(),
        "core/releases/legacy.py enthält die historische Patch-Historie",
    )

    require(
        current_file.is_file(),
        "core/releases/current.py enthält die neuen Release-Nodes",
    )

    require(
        wrapper.stat().st_size < 5000,
        "core/release.py bleibt nach dem Split klein",
    )

    require(
        legacy.stat().st_size > 100000,
        "Vollständige historische Patch-Historie bleibt separat erhalten",
    )

    require(
        current_file.stat().st_size < 30000,
        "Aktuelle Release-Datei bleibt klein und wartbar",
    )

    print(
        "✅ Growstar Release-Split Regression vollständig erfolgreich "
        f"({GROWSTAR_VERSION} / {GROWSTAR_INTERNAL_PHASE})"
    )


if __name__ == "__main__":
    main()
