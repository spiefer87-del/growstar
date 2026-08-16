#!/usr/bin/env python3
"""Phase 4Q – stabile Regression für das Release-/Patch-System."""

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
        "phase4q_release",
        ROOT / "core" / "release.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    ast.parse(read("core/release.py"), filename="core/release.py")
    print("✅ Python-Syntax core/release.py")

    release_text = read("core/release.py")
    notes_text = read("templates/patch_notes.html")
    release = load_release()

    current = release.current_release()
    summary = release.release_summary()
    history = release.release_history()
    version_parts = str(release.GROWSTAR_VERSION or "").split(".")

    require(
        len(version_parts) == 3 and all(part.isdigit() for part in version_parts),
        "Aktuelle Growstar-Version verwendet MAJOR.MINOR.PATCH",
    )
    require(
        current["version"] == release.GROWSTAR_VERSION == summary["version"],
        "Aktuelle Version stammt aus einer einzigen Release-Quelle",
    )
    require(
        history and history[0]["version"] == release.GROWSTAR_VERSION,
        "Neuester Release-Eintrag steht an erster Stelle",
    )
    require(
        all(item.get("changes") and item.get("tests") for item in history),
        "Jeder Release enthält Änderungen und Testhinweise",
    )
    require(
        "Was wurde geändert?" in notes_text
        and "Was sollte nach dem Update getestet werden?" in notes_text
        and "Vorherige Änderungen" in notes_text,
        "Patch-Seite zeigt Änderungen, Tests und Historie",
    )
    require(
        "growstar_release_tests_${version}" in notes_text,
        "Test-Checkliste bleibt pro Version lokal gespeichert",
    )

    optional_checks = {
        "routes/release.py": (
            '"/system/patch-notes"',
            '"/api/system/version"',
            "@app.context_processor",
        ),
        "app.py": (
            "register_release_routes(app)",
            "GROWSTAR_VERSION=GROWSTAR_VERSION",
        ),
        "auth/policy.py": (
            '"/system/patch-notes": require("dashboard.view")',
            '"/api/system/version": require("dashboard.view")',
        ),
    }
    for rel, tokens in optional_checks.items():
        path = ROOT / rel
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        if rel.endswith(".py"):
            ast.parse(content, filename=rel)
        require(
            all(token in content for token in tokens),
            f"Release-Infrastruktur bleibt in {rel} registriert",
        )

    forbidden = (
        "core.actuators",
        "core.control",
        "core.safety",
        "services.shelly",
        "services.safety",
        "switch_shelly",
        "set_device",
    )
    require(
        not any(token in release_text for token in forbidden),
        "Release-Metadaten bleiben ohne Hardware-, Safety- oder Regelungszugriff",
    )

    print("✅ Phase 4Q Release-Infrastruktur vollständig")


if __name__ == "__main__":
    main()
