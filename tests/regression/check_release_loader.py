#!/usr/bin/env python3
"""Validate all Growstar release nodes through the real release loader."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    from core.releases.loader import PATCH_RELEASES, RELEASE_MODULES

    require(
        len(PATCH_RELEASES) == len(RELEASE_MODULES),
        "Release-Metadaten und Modulnamen sind vollständig synchron",
    )

    require(
        len(PATCH_RELEASES) > 0,
        "Mindestens ein Patch-Release wurde durch den echten Loader geladen",
    )

    versions = [item["version"] for item in PATCH_RELEASES]
    require(
        len(versions) == len(set(versions)),
        "Alle Release-Versionen sind eindeutig",
    )

    for module_name, release in zip(RELEASE_MODULES, PATCH_RELEASES):
        require(
            isinstance(release.get("tests"), (tuple, list)),
            f"{module_name} besitzt ein gültiges tests-Feld",
        )

    print(
        f"✅ Release-Loader vollständig erfolgreich: "
        f"{len(PATCH_RELEASES)} Release-Nodes validiert"
    )


if __name__ == "__main__":
    main()
