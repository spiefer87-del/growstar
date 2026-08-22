#!/usr/bin/env python3
"""Permanent regression for Growstar's file-per-release architecture.

This test intentionally contains no hard-coded current Growstar version,
phase, or release date. It verifies architecture invariants that must remain
true for every future patch.
"""

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
    text = str(value or "")
    parts = text.split(".")

    require(
        len(parts) == 3 and all(part.isdigit() for part in parts),
        f"Version {text!r} verwendet Major.Minor.Patch",
    )

    return tuple(int(part) for part in parts)


def expected_module_name(release):
    version = str(release["version"]).replace(".", "_")
    phase = (
        str(release["phase"])
        .lower()
        .replace(".", "_")
        .replace("-", "_")
    )
    return f"r_{version}_{phase}"


def main():
    releases_dir = ROOT / "core" / "releases"

    require(
        len(PATCH_RELEASES) >= 1,
        "Automatischer Release-Loader findet mindestens einen Patch-Release",
    )

    require(
        len(LEGACY_RELEASES) >= 1,
        "Legacy-Historie ist weiterhin vorhanden",
    )

    require(
        CURRENT_RELEASES == PATCH_RELEASES,
        "CURRENT_RELEASES bleibt als kompatibler Alias auf PATCH_RELEASES erhalten",
    )

    require(
        RELEASES == tuple(PATCH_RELEASES) + tuple(LEGACY_RELEASES),
        "Öffentliche RELEASES-Historie setzt Patch-Releases und Legacy exakt zusammen",
    )

    patch_versions = [item["version"] for item in PATCH_RELEASES]

    require(
        patch_versions
        == sorted(
            patch_versions,
            key=version_key,
            reverse=True,
        ),
        "Patch-Releases sind numerisch absteigend sortiert",
    )

    require(
        len(patch_versions) == len(set(patch_versions)),
        "Jede Patch-Version kommt genau einmal vor",
    )

    identities = [
        (item.get("version"), item.get("phase"))
        for item in RELEASES
    ]

    require(
        len(identities) == len(set(identities)),
        "Gesamte Release-Historie enthält keine Versions-/Phasen-Duplikate",
    )

    newest = PATCH_RELEASES[0]

    require(
        RELEASES[0] == newest,
        "Der höchste Patch-Release ist gleichzeitig der aktuelle öffentliche Release",
    )

    require(
        GROWSTAR_VERSION == newest["version"],
        "GROWSTAR_VERSION folgt dynamisch dem höchsten Release-Node",
    )

    require(
        GROWSTAR_INTERNAL_PHASE == newest["phase"],
        "GROWSTAR_INTERNAL_PHASE folgt dynamisch dem höchsten Release-Node",
    )

    require(
        GROWSTAR_RELEASE_DATE == newest["date"],
        "GROWSTAR_RELEASE_DATE folgt dynamisch dem höchsten Release-Node",
    )

    current = current_release()

    require(
        current["version"] == newest["version"],
        "current_release liefert dynamisch die aktuelle Version",
    )

    require(
        current["phase"] == newest["phase"],
        "current_release liefert dynamisch die aktuelle Phase",
    )

    require(
        current["date"] == newest["date"],
        "current_release liefert dynamisch das aktuelle ISO-Datum",
    )

    expected_date_label = datetime.date.fromisoformat(
        newest["date"]
    ).strftime("%d.%m.%Y")

    require(
        current["date_label"] == expected_date_label,
        f"Deutsches Datumslabel wird dynamisch erzeugt ({expected_date_label})",
    )

    summary = release_summary()

    require(
        summary == {
            "version": newest["version"],
            "release_date": newest["date"],
            "phase": newest["phase"],
            "title": newest["title"],
        },
        "release_summary wird ausschließlich aus dem aktuellen Release erzeugt",
    )

    current_copy = current_release()
    current_copy["changes"].append("REGRESSION-MUTATION")

    require(
        "REGRESSION-MUTATION" not in PATCH_RELEASES[0]["changes"],
        "current_release liefert eine defensive Kopie",
    )

    history_copy = release_history()

    require(
        len(history_copy) == len(RELEASES),
        "release_history liefert die vollständige kombinierte Historie",
    )

    history_copy[0]["tests"].append("REGRESSION-MUTATION")

    require(
        "REGRESSION-MUTATION" not in RELEASES[0]["tests"],
        "release_history liefert defensive Kopien",
    )

    node_files = sorted(releases_dir.glob("r_*.py"))
    node_stems = {path.stem for path in node_files}

    require(
        len(node_files) == len(PATCH_RELEASES),
        "Auf der Platte existiert genau eine Release-Datei pro Patch-Release",
    )

    require(
        node_stems == set(RELEASE_MODULES),
        "Loader-Discovery entspricht exakt den vorhandenen Release-Dateien",
    )

    expected_modules = {
        expected_module_name(item)
        for item in PATCH_RELEASES
    }

    require(
        set(RELEASE_MODULES) == expected_modules,
        "Dateinamen entsprechen dynamisch Version und Phase ihrer Release-Nodes",
    )

    for path in node_files:
        text = path.read_text(encoding="utf-8")

        require(
            path.stat().st_size < 12000,
            f"{path.name} bleibt eine kleine einzelne Release-Datei",
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

    loader = releases_dir / "loader.py"
    current_wrapper = releases_dir / "current.py"
    public_wrapper = ROOT / "core" / "release.py"
    legacy = releases_dir / "legacy.py"

    require(
        loader.is_file(),
        "Automatischer Release-Loader ist vorhanden",
    )

    require(
        current_wrapper.is_file(),
        "Kompatibilitäts-Wrapper current.py ist vorhanden",
    )

    require(
        public_wrapper.is_file(),
        "Öffentliche Release-Schnittstelle core/release.py ist vorhanden",
    )

    require(
        legacy.is_file(),
        "Legacy-Historie ist separat vorhanden",
    )

    require(
        loader.stat().st_size < 8000,
        "loader.py bleibt klein und wartbar",
    )

    require(
        current_wrapper.stat().st_size < 1500,
        "current.py bleibt ein kleiner Kompatibilitäts-Wrapper",
    )

    require(
        public_wrapper.stat().st_size < 5000,
        "core/release.py bleibt eine kleine öffentliche Schnittstelle",
    )

    current_text = current_wrapper.read_text(encoding="utf-8")

    require(
        "RELEASE = {" not in current_text
        and '"version"' not in current_text
        and "'version'" not in current_text,
        "current.py enthält dauerhaft keine Release-Dictionaries",
    )

    require(
        RELEASES[len(PATCH_RELEASES)] == LEGACY_RELEASES[0],
        "Übergang zur Legacy-Historie bleibt lückenlos",
    )

    require(
        RELEASES[-1] == LEGACY_RELEASES[-1],
        "Historisches Ende der Release-Historie bleibt unverändert erreichbar",
    )

    print(
        "✅ Growstar Release-System Regression vollständig erfolgreich "
        f"({GROWSTAR_VERSION} / {GROWSTAR_INTERNAL_PHASE})"
    )


if __name__ == "__main__":
    main()
