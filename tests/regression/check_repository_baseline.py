#!/usr/bin/env python3
"""Growstar – konsolidierter Repository-Baseline-Test.

Der Test ist read-only:
- keine Shelly-Schreibzugriffe
- keine NetworkManager-Mutationen
- kein systemd-Neustart
"""

from pathlib import Path
import ast
import importlib.util
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def ok(message):
    print("✅", message)


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    ok(message)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def tracked_paths():
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "Der Baseline-Test muss innerhalb des Growstar-Git-Repositories laufen"
        ) from exc

    return {
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    }


def load_release():
    spec = importlib.util.spec_from_file_location(
        "growstar_baseline_release",
        ROOT / "core/release.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def check_python_syntax(tracked):
    python_files = sorted(
        path for path in tracked
        if path.endswith(".py")
        and not path.startswith(".git/")
    )

    for rel in python_files:
        source = read(rel)
        ast.parse(source, filename=rel)

    ok(f"Python-Syntax aller {len(python_files)} getrackten Python-Dateien")


def check_template_references(tracked):
    pattern = re.compile(
        r"""render_template\(\s*["']([^"']+\.html)["']""",
        re.MULTILINE,
    )

    referenced = set()

    for rel in sorted(tracked):
        if not rel.endswith(".py"):
            continue
        if not (
            rel == "app.py"
            or rel.startswith("routes/")
            or rel.startswith("plant_management/")
        ):
            continue

        try:
            source = read(rel)
        except UnicodeDecodeError:
            continue

        referenced.update(pattern.findall(source))

    missing = sorted(
        name
        for name in referenced
        if f"templates/{name}" not in tracked
    )

    require(
        not missing,
        "Alle literalen render_template()-Ziele besitzen ein getracktes Template"
        + ("" if not missing else ": " + ", ".join(missing)),
    )


def main():
    tracked = tracked_paths()
    release = load_release()

    current_release = release.RELEASES[0]
    current_version = str(current_release.get("version") or "")
    current_phase = str(current_release.get("phase") or "")

    require(
        release.GROWSTAR_VERSION == current_version
        and release.GROWSTAR_INTERNAL_PHASE == current_phase,
        (
            "Release-Konstanten folgen dem obersten RELEASES-Eintrag "
            f"({current_version} / {current_phase})"
        ),
    )

    require(
        re.fullmatch(r"\d+\.\d+\.\d+", current_version) is not None
        and bool(current_phase.strip()),
        "Aktuelle Growstar-Version und interne Phase sind formal gültig",
    )

    root_checks = sorted(
        path
        for path in tracked
        if "/" not in path
        and path.startswith("check_")
        and path.endswith(".py")
    )
    require(
        not root_checks,
        "Repository-Root enthält keine historischen check_*.py mehr"
        + ("" if not root_checks else ": " + ", ".join(root_checks)),
    )

    forbidden = {
        "app_backup.py",
        "main.py",
        "presets.py",
        "style.css",
        "tools/test.py",
        "templates/admin/new.py",
        "templates/heizung.html",
        "templates/abluft.html",
        "templates/licht.html",
        "templates/ventilator.html",
        "templates/tagebuch.html",
        "templates/pflanzendaten.html",
        "pico_sensor_01/config.py",
        "pico_sensor_02/config.py",
    }
    still_tracked = sorted(forbidden.intersection(tracked))
    require(
        not still_tracked,
        "Backup-, Prototyp-, Legacy- und Pico-Secret-Dateien sind nicht mehr getrackt"
        + ("" if not still_tracked else ": " + ", ".join(still_tracked)),
    )

    required = {
        "app.py",
        "config.json",
        "profiles.json",
        "core/profile.py",
        "routes/profile.py",
        "core/restart_policy.py",
        "services/restart_policy.py",
        "routes/restart_policy.py",
        "services/network.py",
        "install/growstar_network_helper.py",
        "install/install_network_permissions.sh",
        "install/growstar.service.in",
        "install/install_growstar_service.sh",
        "install/activate_phase4t_without_old_shutdown.sh",
        "tools/prepare_phase4t_restart.py",
        "templates/device_control.html",
        "templates/restart_policy.html",
        "pico_sensor_01/config.example.py",
        "pico_sensor_02/config.example.py",
        "SECURITY.md",
        "docs/REPOSITORY_BASELINE.md",
        "tests/README.md",
        "tests/regression/check_repository_baseline.py",
    }
    missing_required = sorted(required - tracked)
    require(
        not missing_required,
        "Aktive Laufzeit-, Installations- und Baseline-Dateien bleiben erhalten"
        + ("" if not missing_required else ": " + ", ".join(missing_required)),
    )

    ignore = read(".gitignore")
    for rule in (
        "instance/",
        "backups/",
        "tent_configs/",
        "tests.json",
        "pico_sensor_*/config.py",
    ):
        require(rule in ignore, f".gitignore schützt {rule}")

    for example in (
        "pico_sensor_01/config.example.py",
        "pico_sensor_02/config.example.py",
    ):
        text = read(example)
        require(
            'SSID = "DEIN_WLAN_NAME"' in text
            and 'PASSWORD = "DEIN_WLAN_PASSWORT"' in text,
            f"{example} enthält ausschließlich Platzhalter-Credentials",
        )
        require(
            not re.search(r'PASSWORD\s*=\s*["\']\d{12,}["\']', text),
            f"{example} enthält kein offensichtlich produktives numerisches WLAN-Passwort",
        )

    app = read("app.py")
    require(
        "apply_shutdown_restart_policy" in app,
        "app.py verwendet weiterhin die Phase-4T-Restart-Policy",
    )
    require(
        "register_profile_routes(app)" in app
        and "register_restart_policy_routes(app)" in app,
        "Profile- und Restart-Policy-Routen bleiben registriert",
    )

    profile = read("core/profile.py")
    require(
        'PROFILE_FILE = "profiles.json"' in profile,
        "profiles.json bleibt bewusst aktiver Profilkatalog/Fallback",
    )

    dashboard = read("routes/dashboard.py")
    require(
        '"device_control.html"' in dashboard,
        "Geräteansichten verwenden weiterhin das generische device_control.html",
    )

    service_unit = read("install/growstar.service.in")
    require(
        "app:flask_app" in service_unit and "Restart=always" in service_unit,
        "Growstar-Systemdienst bleibt Gunicorn/app:flask_app mit Restart=always",
    )

    require(
        "shell=True" not in read("services/network.py")
        and "shell=True" not in read("install/growstar_network_helper.py"),
        "Netzwerkpfad bleibt ohne shell=True",
    )

    require(
        "SIGSTOP" in read("install/activate_phase4t_without_old_shutdown.sh")
        and "PROJECT_ROOT" in read("tools/prepare_phase4t_restart.py"),
        "Historischer sicherer Phase-4T-Upgradepfad bleibt erhalten",
    )

    check_template_references(tracked)
    check_python_syntax(tracked)

    print(f"✅ Growstar Repository-Baseline vollständig · {release.GROWSTAR_VERSION} / Phase {release.GROWSTAR_INTERNAL_PHASE}")


if __name__ == "__main__":
    main()
