"""Automatic loader for Growstar patch release nodes.

Every post-legacy release lives in exactly one ``r_*.py`` module and exports a
single ``RELEASE`` mapping. New releases therefore require only a new module;
this loader and older release files do not need to be edited.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
import pkgutil
import re


_RELEASE_MODULE_RE = re.compile(r"^r_\d+(?:_\d+){2}_.+$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _version_key(value):
    text = str(value or "")
    if not _VERSION_RE.fullmatch(text):
        raise ValueError(f"Ungültige Growstar-Version im Release-Node: {text!r}")
    return tuple(int(part) for part in text.split("."))


def _validate_release(item, module_name):
    if not isinstance(item, dict):
        raise TypeError(
            f"{module_name} muss RELEASE als Dictionary exportieren"
        )

    required = (
        "version",
        "date",
        "phase",
        "title",
        "summary",
        "changes",
        "tests",
    )

    missing = [
        key
        for key in required
        if key not in item
    ]

    if missing:
        raise ValueError(
            f"{module_name}: fehlende Release-Felder: {', '.join(missing)}"
        )

    _version_key(item["version"])

    if not _DATE_RE.fullmatch(str(item.get("date") or "")):
        raise ValueError(
            f"{module_name}: ungültiges Release-Datum {item.get('date')!r}"
        )

    for key in ("phase", "title", "summary"):
        if not str(item.get(key) or "").strip():
            raise ValueError(
                f"{module_name}: leeres Release-Feld {key}"
            )

    for key in ("changes", "tests"):
        value = item.get(key)
        if not isinstance(value, (tuple, list)):
            raise TypeError(
                f"{module_name}: {key} muss Tuple oder Liste sein"
            )

    return item


def _discover_release_modules():
    package_dir = Path(__file__).resolve().parent

    names = sorted(
        info.name
        for info in pkgutil.iter_modules([str(package_dir)])
        if _RELEASE_MODULE_RE.fullmatch(info.name)
    )

    releases = []
    module_names = []

    for name in names:
        module = import_module(
            f"{__package__}.{name}"
        )

        release = _validate_release(
            getattr(module, "RELEASE", None),
            name,
        )

        releases.append(release)
        module_names.append(name)

    identities = [
        str(item["version"])
        for item in releases
    ]

    duplicates = sorted(
        version
        for version in set(identities)
        if identities.count(version) > 1
    )

    if duplicates:
        raise ValueError(
            "Doppelte Growstar-Release-Versionen: "
            + ", ".join(duplicates)
        )

    ordered = sorted(
        releases,
        key=lambda item: _version_key(item["version"]),
        reverse=True,
    )

    ordered_names = [
        module_name
        for _, module_name in sorted(
            zip(
                releases,
                module_names,
            ),
            key=lambda pair: _version_key(
                pair[0]["version"]
            ),
            reverse=True,
        )
    ]

    return tuple(ordered), tuple(ordered_names)


PATCH_RELEASES, RELEASE_MODULES = _discover_release_modules()

# Backward-compatible name used by the CORE.R1/CORE.R2 transition and older
# infrastructure code. It is now generated automatically instead of being
# maintained in a growing current.py.
CURRENT_RELEASES = PATCH_RELEASES


__all__ = (
    "PATCH_RELEASES",
    "CURRENT_RELEASES",
    "RELEASE_MODULES",
)
