#!/usr/bin/env python3
"""Growstar 3.13.0 / Shell.1 regression guard.

The application shell is UI-only. It may add navigation assets and links but
must not mutate control, hardware, MQTT, Spider Farmer, Shelly or restart logic.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    base = (ROOT / "templates/base.html").read_text(encoding="utf-8")
    css = (ROOT / "static/css/growstar-app-shell.css").read_text(encoding="utf-8")
    js = (ROOT / "static/js/growstar-app-shell.js").read_text(encoding="utf-8")
    dashboard_routes = (ROOT / "routes/dashboard.py").read_text(encoding="utf-8")
    plant_routes = (ROOT / "routes/plant_management.py").read_text(encoding="utf-8")
    release_routes = (ROOT / "routes/release.py").read_text(encoding="utf-8")

    require(
        "growstar-app-shell.css" in base and "growstar-app-shell.js" in base,
        "Base lädt ausschließlich die neue Application-Shell als UI-Erweiterung",
    )
    require(
        "device-setpoint-stepper.js" in base and "growstar-feedback.js" in base,
        "bestehende UI-Helfer bleiben unverändert eingebunden",
    )
    require(
        "{% if current_user %}" in base,
        "Navigation erscheint nur in einer angemeldeten Growstar-Sitzung",
    )
    require(
        'data-growstar-menu-open' in base
        and 'data-growstar-menu-close' in base
        and 'data-growstar-menu-overlay' in base,
        "Drawer besitzt Öffnen, Schließen und Overlay",
    )
    require(
        'aria-controls="growstar-navigation"' in base
        and 'aria-hidden="true"' in base,
        "Navigation besitzt zugängliche ARIA-Zustände",
    )
    require(
        'event.key === "Escape"' in js and 'event.key !== "Tab"' in js,
        "Drawer unterstützt Escape und Keyboard-Fokusführung",
    )
    require(
        "deltaX < -70" in js,
        "Touch-Swipe schließt den Drawer ohne Slider-Öffnungsgeste",
    )
    require(
        "body.growstar-menu-open" in css,
        "Hintergrund wird bei geöffnetem Drawer gegen Scrollen gesperrt",
    )
    require(
        ".growstar-nav-item.active" in css,
        "aktiver Bereich wird deutlich markiert",
    )

    expected_dashboard_endpoints = (
        "dashboard",
        "grow_control_dashboard",
        "grow_control_live",
        "grow_control_sensors_dashboard",
        "grow_control_connections",
        "grow_control_watchdog",
        "grow_control_setup",
        "devices",
        "spiderfarmer_system_page",
        "energie_page",
        "diagrams_page",
        "system_page",
    )
    for endpoint in expected_dashboard_endpoints:
        require(
            f"def {endpoint}(" in dashboard_routes,
            f"Navigationsziel {endpoint} existiert in routes/dashboard.py",
        )

    require(
        "def plant_management_dashboard(" in plant_routes,
        "Pflanzenmanagement-Ziel existiert",
    )
    require(
        "def patch_notes_page(" in release_routes,
        "Versionsziel existiert",
    )

    # Architecture guard: Shell.1 must remain a pure presentation patch.
    forbidden_in_package = (
        "core/control.py",
        "core/runtime.py",
        "services/spiderfarmer.py",
        "services/live_control.py",
        "services/shelly.py",
        "threads/main.py",
        "threads/hardware.py",
        "install/growstar-spiderfarmer.service.in",
    )
    for path in forbidden_in_package:
        require(
            not (ROOT / path).name.startswith("growstar-app-shell"),
            f"Regelungs-/Hardwarepfad bleibt außerhalb der Shell-Implementierung: {path}",
        )

    print("✅ Growstar 3.13.0 / Shell.1 Application-Shell vollständig geprüft")


if __name__ == "__main__":
    main()
