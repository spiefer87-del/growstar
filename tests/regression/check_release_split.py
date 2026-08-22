#!/usr/bin/env python3
"""Regression for Growstar's file-per-release architecture."""

from __future__ import annotations

import datetime
from pathlib import Path
import re
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
    PATCH_RELEASES,
    RELEASE_MODULES,
)


def require(condition, message):
    if not condition:
        raise AssertionError(message)

    print("✅", message)


def version_key(value):
    return tuple(
        int(part)
        for part in str(value).split(".")
    )


def main():
    require(
        len(RELEASES) >= 2,
        "Release-Historie enthält aktuellen Release und Vorgänger",
    )

    require(
        len(PATCH_RELEASES) >= 1,
        "Automatischer Patch-Loader findet mindestens einen Release",
    )

    require(
        CURRENT_RELEASES == PATCH_RELEASES,
        "CURRENT_RELEASES bleibt als kompatibler Alias erhalten",
    )

    require(
        len(RELEASE_MODULES) == len(PATCH_RELEASES),
        "Jeder Patch-Release besitzt genau ein entdecktes Release-Modul",
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
        RELEASES == tuple(PATCH_RELEASES) + tuple(LEGACY_RELEASES),
        "RELEASES setzt Einzeldatei-Patches und Legacy-Historie exakt zusammen",
    )

    require(
        RELEASES[len(PATCH_RELEASES)] == LEGACY_RELEASES[0],
        "Übergang von Einzeldatei-Patches zur Legacy-Historie bleibt lückenlos",
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

    patch_versions = [
        item["version"]
        for item in PATCH_RELEASES
    ]

    require(
        patch_versions == sorted(
            patch_versions,
            key=version_key,
            reverse=True,
        ),
        "Patch-Releases sind numerisch nach Version absteigend sortiert",
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

    require(
        len(patch_versions) == len(set(patch_versions)),
        "Jede neue Growstar-Version besitzt genau einen Patch-Release",
    )

    current = current_release()

    require(
        current["version"] == newest["version"]
        and current["phase"] == newest["phase"],
        "current_release liefert den aktuell obersten Release",
    )

    expected_date_label = datetime.date.fromisoformat(
        newest["date"]
    ).strftime("%d.%m.%Y")

    require(
        current["date_label"] == expected_date_label,
        (
            "current_release erzeugt das deutsche Datumslabel dynamisch "
            f"({expected_date_label})"
        ),
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

    releases_dir = ROOT / "core" / "releases"
    wrapper = ROOT / "core" / "release.py"
    legacy = releases_dir / "legacy.py"
    loader = releases_dir / "loader.py"
    current_file = releases_dir / "current.py"

    require(
        wrapper.is_file(),
        "core/release.py existiert als öffentliche Release-Schnittstelle",
    )

    require(
        legacy.is_file(),
        "core/releases/legacy.py enthält die historische Patch-Historie",
    )

    require(
        loader.is_file(),
        "core/releases/loader.py übernimmt die automatische Release-Discovery",
    )

    require(
        current_file.is_file(),
        "core/releases/current.py bleibt als kleiner Kompatibilitäts-Wrapper erhalten",
    )

    require(
        wrapper.stat().st_size < 5000,
        "core/release.py bleibt klein",
    )

    require(
        legacy.stat().st_size > 100000,
        "Vollständige historische Patch-Historie bleibt separat erhalten",
    )

    require(
        loader.stat().st_size < 8000,
        "Automatischer Release-Loader bleibt klein und wartbar",
    )

    require(
        current_file.stat().st_size < 1500,
        "current.py wächst nicht mehr und enthält nur noch den Kompatibilitäts-Wrapper",
    )

    current_text = current_file.read_text(
        encoding="utf-8"
    )

    require(
        "RELEASE = {" not in current_text
        and '"version"' not in current_text
        and "'version'" not in current_text,
        "current.py enthält keine Release-Nodes mehr",
    )

    node_files = sorted(
        releases_dir.glob("r_*.py")
    )

    require(
        len(node_files) == len(PATCH_RELEASES),
        "Auf der Platte existiert genau eine Datei pro Patch-Release",
    )

    require(
        {
            path.stem
            for path in node_files
        }
        == set(RELEASE_MODULES),
        "Loader-Discovery und vorhandene Release-Dateien stimmen exakt überein",
    )

    for path in node_files:
        require(
            path.stat().st_size < 12000,
            f"{path.name} bleibt eine kleine einzelne Release-Datei",
        )

        text = path.read_text(
            encoding="utf-8"
        )

        require(
            len(
                re.findall(
                    r"(?m)^RELEASE\s*=",
                    text,
                )
            )
            == 1,
            f"{path.name} exportiert genau einen RELEASE-Node",
        )

    require(
        newest["version"] == "3.11.8"
        and newest["phase"] == "CORE.R3",
        "CORE.R3-Migration meldet 3.11.8 / CORE.R3 als aktuellen Release",
    )

    print(
        "✅ Growstar Einzeldatei-Release-Regression vollständig erfolgreich "
        f"({GROWSTAR_VERSION} / {GROWSTAR_INTERNAL_PHASE})"
    )


if __name__ == "__main__":
    main()
