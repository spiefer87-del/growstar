#!/usr/bin/env python3
"""Phase 4T.1 – Aktivierungsbootstrap und sichtbarer Setup-Einstieg."""

from pathlib import Path
import ast
import importlib.util
import sys

ROOT = Path(__file__).resolve().parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def load_module(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    for rel in (
        "core/release.py",
        "tools/prepare_phase4t_restart.py",
        "check_phase4t1_activation_setup.py",
    ):
        ast.parse(read(rel), filename=rel)
        print("✅ Python-Syntax", rel)

    release = load_module("phase4t1_release", "core/release.py")

    require(
        release.GROWSTAR_VERSION == "3.7.10"
        and release.GROWSTAR_INTERNAL_PHASE == "4T.1",
        "Growstar wurde auf Version 3.7.10 / Phase 4T.1 erhöht",
    )

    prepare = read("tools/prepare_phase4t_restart.py")
    root_line = prepare.index("PROJECT_ROOT = Path(__file__).resolve().parents[1]")
    path_line = prepare.index("sys.path.insert(0, project_root_text)")
    core_line = prepare.index("from core.runtime import")

    require(
        root_line < path_line < core_line,
        "Projekt-Root wird vor allen core-Imports in sys.path eingebunden",
    )
    require(
        "from pathlib import Path" in prepare
        and "project_root_text = str(PROJECT_ROOT)" in prepare,
        "Vorbereitungsskript ist für direkten Start aus tools/ selbsttragend",
    )

    activate = read("install/activate_phase4t_without_old_shutdown.sh")
    require(
        'PYTHONPATH="${PROJECT_DIR}${PYTHONPATH:+:${PYTHONPATH}}"' in activate,
        "Aktivierungsskript übergibt PROJECT_DIR zusätzlich als PYTHONPATH",
    )
    require(
        'sudo -u "${SERVICE_USER}" env' in activate
        and 'python3 "${PREPARE}"' in activate,
        "Vorbereitung läuft weiterhin als erkannter Growstar-Dienstbenutzer",
    )
    require(
        "SIGCONT" in activate
        and "resume_old_service" in activate
        and "trap resume_old_service ERR" in activate,
        "Fehler-Fallback setzt einen eingefrorenen alten Growstar-Prozess fort",
    )

    stop_cmd = 'systemctl kill --kill-whom=all --signal=SIGSTOP "${SERVICE}"'
    prepare_cmd = 'python3 "${PREPARE}"'
    kill_cmd = 'systemctl kill --kill-whom=all --signal=SIGKILL "${SERVICE}"'
    require(
        activate.index(stop_cmd)
        < activate.index(prepare_cmd)
        < activate.index(kill_cmd),
        "Sichere Aktivierungsreihenfolge Freeze -> Policy -> alter Worker bleibt erhalten",
    )

    setup = read("templates/grow_control_setup.html")
    require(
        "Neustart-Verhalten" in setup
        and 'class="setup-tool"' in setup,
        "Grow-Control-Setup enthält die neue Neustart-Verhalten-Kachel",
    )
    require(
        "url_for('grow_control_restart_policy')" in setup,
        "Setup-Kachel verlinkt auf die bestehende Restart-Policy-Seite",
    )
    require(
        "Zustand bei einem" in setup
        and "sicher AUS" in setup,
        "Kachel beschreibt KEEP/OFF verständlich",
    )

    require(
        "shell=True" not in prepare,
        "Vorbereitungsskript führt weiterhin keine Shell-Kommandos aus",
    )

    print("✅ Phase 4T.1 Aktivierungsfix und Setup-Einstieg vollständig")


if __name__ == "__main__":
    main()
