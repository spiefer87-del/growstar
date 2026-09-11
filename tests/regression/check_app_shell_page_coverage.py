#!/usr/bin/env python3
"""Regression für die App-Shell auf allen aktiven Verwaltungsseiten."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def read(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def main():
    shell_templates = (
        "templates/devices.html",
        "templates/gateway.html",
        "templates/blu_device.html",
        "templates/spiderfarmer.html",
        "templates/profiles.html",
        "templates/settings.html",
        "templates/sensoren.html",
        "templates/diagrams.html",
        "templates/environment_history.html",
    )
    for relative_path in shell_templates:
        source = read(relative_path)
        require(
            source.startswith('{% extends "base.html" %}')
            and "{% block page %}" in source
            and "<!DOCTYPE html>" not in source
            and "<body" not in source,
            f"{Path(relative_path).name} verwendet die zentrale Hamburger-Navigation",
        )

    routes = read("routes/dashboard.py")
    base = read("templates/base.html")
    hardware = read("templates/hardware/dashboard.html")
    require(
        'return redirect(url_for("hardware_management_dashboard"), code=302)' in routes
        and "url_for('system_page')" not in base
        and "url_for('system_page')" not in hardware,
        "Das alte System-Doppeldashboard ist nicht mehr als Navigation erreichbar",
    )
    require(
        "system_metrics.html" in read("routes/watchdog.py")
        and "watchdog_system_data" in base,
        "Aktuelle Raspberry-Systemdaten bleiben über Watchdog erreichbar",
    )
    print("✅ App-Shell-Abdeckung und Systemseiten-Bereinigung vollständig geprüft")


if __name__ == "__main__":
    main()
