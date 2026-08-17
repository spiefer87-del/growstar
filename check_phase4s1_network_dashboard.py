#!/usr/bin/env python3
"""Phase 4S.1 – Netzwerk-Kachel im Grow-Control-Dashboard."""

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
        "phase4s1_release",
        ROOT / "core" / "release.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    ast.parse(read("core/release.py"), filename="core/release.py")
    ast.parse(read("check_phase4s1_network_dashboard.py"), filename="check_phase4s1_network_dashboard.py")
    print("✅ Python-Syntax core/release.py")
    print("✅ Python-Syntax check_phase4s1_network_dashboard.py")

    release = load_release()
    require(
        release.GROWSTAR_VERSION == "3.7.1"
        and release.GROWSTAR_INTERNAL_PHASE == "4S.1",
        "Growstar wurde auf Version 3.7.1 / Phase 4S.1 erhöht",
    )

    html = read("templates/grow_control_dashboard.html")

    require(
        '<h3>Netzwerk</h3>' in html,
        "Grow-Control-Dashboard enthält die Netzwerk-Kachel",
    )
    require(
        "url_for('system_network_page')" in html,
        "Netzwerk-Kachel nutzt den registrierten Netzwerk-Endpoint",
    )
    require(
        'class="module-card network"' in html
        and ".network { --module-glow:" in html,
        "Netzwerk-Kachel ist in das bestehende Modul-Layout integriert",
    )

    settings_start = html.find("{% if has_permission('settings.view') %}")
    settings_end = html.find("{% endif %}", settings_start)
    network_pos = html.find("<h3>Netzwerk</h3>")

    require(
        settings_start != -1
        and settings_end != -1
        and settings_start < network_pos < settings_end,
        "Netzwerk-Kachel liegt innerhalb des settings.view-Berechtigungsblocks",
    )

    require(
        "services/network.py" not in release.RELEASES[0]["changes"],
        "Patch Note beschreibt den UI-Patch ohne eine Netzwerklogik-Änderung vorzutäuschen",
    )
    require(
        any("read-only" in item for item in release.RELEASES[0]["changes"]),
        "Patch Note hält fest, dass Phase 4S.1 read-only bleibt",
    )

    print("✅ Phase 4S.1 Netzwerk-Dashboard vollständig")


if __name__ == "__main__":
    main()
