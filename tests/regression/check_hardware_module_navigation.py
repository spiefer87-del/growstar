#!/usr/bin/env python3
"""Regression für das eigenständige Hardware-&-Setup-Modul."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from auth.policy import permission_requirement


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    base = (ROOT / "templates/base.html").read_text(encoding="utf-8")
    landing = (ROOT / "templates/hardware/dashboard.html").read_text(encoding="utf-8")
    grow = (ROOT / "templates/grow_control_dashboard.html").read_text(encoding="utf-8")
    dashboard = (ROOT / "templates/dashboard.html").read_text(encoding="utf-8")
    routes = (ROOT / "routes/dashboard.py").read_text(encoding="utf-8")
    devices = (ROOT / "templates/devices.html").read_text(encoding="utf-8")
    connections = (ROOT / "templates/connections.html").read_text(encoding="utf-8")
    camera = (ROOT / "templates/plants/camera.html").read_text(encoding="utf-8")

    require(
        'id="growstar-hardware-submenu"' in base
        and "growstar_hardware_active" in base
        and "<strong>Hardware &amp; Setup</strong>" in base
        and "hardware_management_dashboard" in dashboard,
        "Hardware & Setup ist ein eigenständiges Haupt- und Dashboardmodul",
    )
    require(
        '@app.route("/hardware")' in routes
        and "templates/hardware" not in routes
        and "Geräte &amp; Datenquellen" in landing
        and "Setup &amp; Raspberry" in landing,
        "Die Hardware-Startseite trennt Geräteverwaltung und Raspberry-Setup",
    )
    for endpoint in (
        "devices", "grow_control_sensors_dashboard", "grow_control_connections",
        "spiderfarmer_system_page", "grow_control_watchdog", "grow_control_setup",
        "system_network_page", "growstar_notifications_page",
    ):
        require(f"url_for('{endpoint}')" in landing, f"Hardware-Startseite verlinkt {endpoint}")

    require(
        '@app.route("/system")' in routes
        and 'redirect(url_for("hardware_management_dashboard"), code=302)' in routes
        and "url_for('system_page')" not in landing
        and "url_for('system_page')" not in base,
        "Das veraltete System-Doppeldashboard ist entfernt und seine URL bleibt kompatibel",
    )
    require(
        "url_for('devices')" not in grow
        and "url_for('grow_control_connections')" not in grow
        and "url_for('grow_control_setup')" not in grow
        and "System &amp; Infrastruktur" not in grow,
        "Technische Infrastruktur ist aus dem Grow-Control-Dashboard entfernt",
    )
    require(
        "growcam_hardware_configure" in connections
        and "cameras=growcam_public_configs()" in routes
        and "tents=tent_manager.list_tents()" in routes
        and "Kamera-IP" not in devices
        and "Kamera-IP" in connections
        and "RTSP-Port" in connections
        and "RTSP-Pfad" in connections
        and "Kamera-IP" not in camera
        and "RTSP-Port" not in camera,
        "Die technische GrowCam-Verbindung wird ausschließlich unter Verbindungen bearbeitet",
    )
    require(
        permission_requirement("/hardware", "GET").mode == "any"
        and permission_requirement("/grow-control/sensors", "GET").permissions == ("hardware.view",)
        and permission_requirement("/grow-control/setup", "GET").permissions == ("settings.view",)
        and permission_requirement("/devices/growcam/konfiguration", "POST").permissions == ("hardware.configure",),
        "Hardwareseiten und Kamera-Verbindung verwenden passende Rollenrechte",
    )

    print("✅ Eigenständiges Hardware-&-Setup-Modul vollständig geprüft")


if __name__ == "__main__":
    main()
