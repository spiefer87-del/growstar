#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "tests" / "regression" / "check_repository_baseline.py"
CURRENT = ROOT / "core" / "releases" / "current.py"

VERSION = "3.11.4"
PHASE = "CORE.R2"

RELEASE_NODE = '''    {
        "version": "3.11.4",
        "date": "2026-08-22",
        "phase": "CORE.R2",
        "title": "Repository-Baseline an Release-Paketstruktur angepasst",
        "summary": (
            "Der Repository-Baseline-Test lädt core.release nach dem CORE.R1-"
            "Split jetzt als reguläres Python-Paketmodul. Dadurch funktionieren "
            "die relativen Importe aus core.release auch im Regressionstest, "
            "ohne die neue Release-Struktur zurückzubauen oder Runtime-Code zu "
            "verändern."
        ),
        "changes": (
            "check_repository_baseline.py lädt core.release nicht länger über ein anonymes spec_from_file_location-Modul, sondern package-aware über importlib.import_module.",
            "Vor dem Import werden eventuell zwischengespeicherte core.release/core.releases-Module entfernt, damit der Test den aktuellen Repository-Stand prüft.",
            "Der Repository-Root wird vor dem Import explizit in sys.path gehalten; relative Importe aus core.release funktionieren dadurch wie im normalen Growstar-Prozess.",
            "core/releases/current.py erhält den neuen Release-Node 3.11.4 / CORE.R2; 3.11.3 / CORE.R1 bleibt direkter Vorgänger.",
            "Keine Runtime-, Hardware-, Sensor-, Shelly-, MQTT-, Netzwerk- oder Spider-Farmer-Datei wird geändert.",
        ),
        "tests": (
            "check_repository_baseline.py muss nach dem Patch ohne ImportError vollständig durchlaufen.",
            "check_release_split.py muss weiterhin die getrennte Release-Historie und die öffentliche core.release-Schnittstelle bestätigen.",
            "check_spiderfarmer_growstar_adapter.py muss weiterhin vollständig grün bleiben.",
            "Ein Syntax-/AST-Check bestätigt beide geänderten Python-Dateien vor dem Schreiben.",
        ),
    },
'''

NEW_LOAD_RELEASE = '''def load_release():
    import importlib

    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    for module_name in (
        "core.release",
        "core.releases",
        "core.releases.current",
        "core.releases.legacy",
    ):
        sys.modules.pop(module_name, None)

    return importlib.import_module("core.release")
'''


def fail(message):
    raise SystemExit(f"❌ {message}")


def atomic_write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(text)
        temp = Path(handle.name)
    temp.replace(path)


def replace_function(source: str, function_name: str, replacement: str) -> str:
    tree = ast.parse(source)
    target = None

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            target = node
            break

    if target is None:
        fail(f"Funktion {function_name} wurde nicht gefunden.")

    lines = source.splitlines(keepends=True)
    start = target.lineno - 1
    end = target.end_lineno

    return "".join(lines[:start]) + replacement.rstrip() + "\n\n" + "".join(lines[end:])


def ensure_sys_import(source: str) -> str:
    tree = ast.parse(source)

    has_sys = any(
        isinstance(node, ast.Import)
        and any(alias.name == "sys" for alias in node.names)
        for node in tree.body
    )

    if has_sys:
        return source

    lines = source.splitlines(keepends=True)
    insert_at = 0

    for index, line in enumerate(lines[:30]):
        if line.startswith("from __future__ import"):
            insert_at = index + 1
            break

    lines.insert(insert_at, "import sys\n")
    return "".join(lines)


def patch_baseline():
    if not BASELINE.exists():
        fail(f"Nicht gefunden: {BASELINE}")

    source = BASELINE.read_text(encoding="utf-8")

    if 'return importlib.import_module("core.release")' in source:
        print("✅ check_repository_baseline.py ist bereits package-aware")
        return

    if "def load_release" not in source:
        fail("load_release() wurde in check_repository_baseline.py nicht gefunden.")

    updated = replace_function(source, "load_release", NEW_LOAD_RELEASE)
    updated = ensure_sys_import(updated)
    ast.parse(updated)

    backup = BASELINE.with_suffix(".py.backup-before-core-r2")
    if not backup.exists():
        shutil.copy2(BASELINE, backup)

    atomic_write(BASELINE, updated)
    print("✅ check_repository_baseline.py package-aware aktualisiert")


def patch_current_release():
    if not CURRENT.exists():
        fail("core/releases/current.py fehlt. CORE.R1 muss zuerst installiert sein.")

    source = CURRENT.read_text(encoding="utf-8")

    if f'"version": "{VERSION}"' in source and f'"phase": "{PHASE}"' in source:
        print("✅ core/releases/current.py enthält CORE.R2 bereits")
        return

    marker = "CURRENT_RELEASES = (\n"
    if marker not in source:
        fail("CURRENT_RELEASES = ( wurde nicht gefunden.")

    updated = source.replace(marker, marker + RELEASE_NODE, 1)
    ast.parse(updated)

    backup = CURRENT.with_suffix(".py.backup-before-core-r2")
    if not backup.exists():
        shutil.copy2(CURRENT, backup)

    atomic_write(CURRENT, updated)
    print("✅ core/releases/current.py auf 3.11.4 / CORE.R2 aktualisiert")


def validate():
    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    for module_name in list(sys.modules):
        if module_name == "core.release" or module_name.startswith("core.releases"):
            sys.modules.pop(module_name, None)

    from core.release import GROWSTAR_VERSION, GROWSTAR_INTERNAL_PHASE, RELEASES

    if GROWSTAR_VERSION != VERSION or GROWSTAR_INTERNAL_PHASE != PHASE:
        fail(
            "Release-Validierung fehlgeschlagen: "
            f"{GROWSTAR_VERSION} / {GROWSTAR_INTERNAL_PHASE}"
        )

    if RELEASES[1].get("version") != "3.11.3" or RELEASES[1].get("phase") != "CORE.R1":
        fail(
            "Direkter Vorgänger ist nicht 3.11.3 / CORE.R1: "
            f"{RELEASES[1].get('version')} / {RELEASES[1].get('phase')}"
        )

    compile(BASELINE.read_text(encoding="utf-8"), str(BASELINE), "exec")
    compile(CURRENT.read_text(encoding="utf-8"), str(CURRENT), "exec")

    print("✅ Growstar meldet 3.11.4 / CORE.R2")
    print("✅ Direkter Vorgänger bleibt 3.11.3 / CORE.R1")
    print("✅ Syntaxprüfung erfolgreich")


def main():
    patch_baseline()
    patch_current_release()
    validate()

    print()
    print("Jetzt ausführen:")
    print("  /usr/bin/python3 tests/regression/check_repository_baseline.py")
    print("  /usr/bin/python3 tests/regression/check_release_split.py")
    print("  /usr/bin/python3 tests/regression/check_spiderfarmer_growstar_adapter.py")


if __name__ == "__main__":
    main()
