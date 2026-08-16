#!/usr/bin/env python3
"""Phase 4Q.1 – Versionsanzeige nur im Management Dashboard."""

from pathlib import Path
import ast
import importlib.util

ROOT = Path(__file__).resolve().parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def load_release():
    spec = importlib.util.spec_from_file_location(
        "phase4q1_release",
        ROOT / "core" / "release.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    ast.parse(read("core/release.py"), filename="core/release.py")
    print("✅ Python-Syntax core/release.py")

    release = load_release()
    base = read("templates/base.html")
    dashboard = read("templates/dashboard.html")
    notes = read("templates/patch_notes.html")

    require(
        release.GROWSTAR_VERSION == "3.6.3"
        and release.GROWSTAR_INTERNAL_PHASE == "4Q.1",
        "Phase 4Q.1 erhöht Growstar auf Version 3.6.3",
    )
    require(
        "growstar-release-chip" not in base
        and "data-growstar-release-style" not in base,
        "Globale schwebende Versionsanzeige ist aus base.html entfernt",
    )
    require(
        'id="dashboard-release-link"' in dashboard
        and "v{{ growstar_release.version }}" in dashboard,
        "Version erscheint als dezenter Link im Management Dashboard",
    )
    require(
        "Management Dashboard" in dashboard
        and "brand-meta" in dashboard,
        "Versionslink sitzt direkt bei der Dashboard-Beschriftung",
    )
    require(
        "dashboard-release-new" in dashboard
        and "growstar_last_seen_version" in dashboard
        and "has-new" in dashboard,
        "NEU-Markierung bleibt auf dem Management Dashboard erhalten",
    )
    require(
        'localStorage.setItem("growstar_last_seen_version", version)' in notes,
        "Öffnen der Patch-Information markiert die Version als gelesen",
    )
    require(
        "growstar_release_tests_${version}" in notes,
        "Persistente Patch-Test-Checkliste bleibt erhalten",
    )
    require(
        "/api/system/version" in notes,
        "Read-only Versions-API bleibt dokumentiert",
    )
    require(
        "switch_shelly" not in base + dashboard + notes
        and "set_device(" not in base + dashboard + notes,
        "Phase 4Q.1 enthält keine Hardware-/Aktorsteuerung",
    )

    print("✅ Phase 4Q.1 Dashboard-Versionsanzeige vollständig")


if __name__ == "__main__":
    main()
