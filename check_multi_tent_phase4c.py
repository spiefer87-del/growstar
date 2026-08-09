#!/usr/bin/env python3
"""Phase 4C: stationsbezogene Unterseiten und Schreib-APIs testen.

Der Test benötigt keine echte Hardware und keine laufende Flask-App. Er prüft
Syntax/Jinja, Rechte, URL-Struktur und die Isolation der Runtime-Konfiguration.
"""

from copy import deepcopy
import ast
import importlib.util
from pathlib import Path

from jinja2 import Environment


ROOT = Path(__file__).parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    python_files = [
        "core/config_update.py",
        "core/devices.py",
        "core/profile.py",
        "routes/config.py",
        "routes/tents.py",
        "routes/sensors.py",
        "routes/device.py",
        "routes/diagrams.py",
        "routes/dashboard.py",
        "auth/policy.py",
    ]
    templates = [
        "templates/grow_control.html",
        "templates/grow_control_dashboard.html",
        "templates/grow_control_sensors.html",
        "templates/temperature.html",
        "templates/humidity.html",
        "templates/vpd.html",
        "templates/settings.html",
        "templates/sensoren.html",
        "templates/device_control.html",
    ]

    for rel in python_files:
        ast.parse(read(rel), filename=rel)

    env = Environment()
    for rel in templates:
        env.parse(read(rel))

    dashboard_routes = read("routes/dashboard.py")
    tent_routes = read("routes/tents.py")
    sensor_routes = read("routes/sensors.py")
    device_routes = read("routes/device.py")
    diagram_routes = read("routes/diagrams.py")
    grow = read("templates/grow_control.html")
    settings = read("templates/settings.html")
    sensors = read("templates/sensoren.html")
    temp = read("templates/temperature.html")
    hum = read("templates/humidity.html")
    vpd = read("templates/vpd.html")
    device_template = read("templates/device_control.html")
    sensor_hub = read("templates/grow_control_sensors.html")

    checks = {
        "Stationsbezogene Temperaturroute": '/grow-control/tents/<tent_id>/temperature' in dashboard_routes,
        "Stationsbezogene Feuchteroute": '/grow-control/tents/<tent_id>/humidity' in dashboard_routes,
        "Stationsbezogene VPD-Route": '/grow-control/tents/<tent_id>/vpd' in dashboard_routes,
        "Stationsbezogene Einstellungsroute": '/grow-control/tents/<tent_id>/settings' in dashboard_routes,
        "Stationsbezogene Sensorroute": '/grow-control/tents/<tent_id>/sensors' in dashboard_routes,
        "Eine generische Geräteroute": '/grow-control/tents/<tent_id>/devices/<device>' in dashboard_routes,
        "Eine generische Gerätevorlage": 'render_template(\n            "device_control.html"' in dashboard_routes,
        "Kein licht2.html nötig": '"licht2.html"' not in dashboard_routes,
        "Kein ventilator2.html nötig": '"ventilator2.html"' not in dashboard_routes,
        "Legacy Temperatur leitet auf Default-Station": 'def temperature_page()' in dashboard_routes and '_default_tent_url("grow_control_tent_temperature")' in dashboard_routes,
        "Legacy Licht2 leitet generisch": 'def licht2_page()' in dashboard_routes and 'device="light2"' in dashboard_routes,
        "Grow-Control Links sind stationsbezogen": "grow_control_tent_temperature" in grow and "grow_control_tent_device" in grow,
        "Gerätekarten sind nicht mehr Legacy-gesperrt": "legacy-detail-link" not in grow,
        "Temperatur nutzt tent_id-Historie": '/api/tents/${encodeURIComponent(TENT_ID)}/history' in temp,
        "Feuchte nutzt tent_id-Historie": '/api/tents/${encodeURIComponent(TENT_ID)}/history' in hum,
        "VPD nutzt tent_id-Historie": '/api/tents/${encodeURIComponent(TENT_ID)}/history' in vpd,
        "Klima-Unterseiten nutzen kein globales /api/history": all('fetch("/api/history' not in x and "fetch('/api/history" not in x for x in (temp, hum, vpd)),
        "Settings liest stationsbezogene Config": '/api/tents/${encodeURIComponent(TENT_ID)}/config' in settings,
        "Settings wechselt Profil stationsbezogen": '/api/tents/${encodeURIComponent(TENT_ID)}/profile/' in settings,
        "Settings nutzt kein globales /api/config": 'fetch("/api/config' not in settings and "fetch('/api/config" not in settings,
        "Sensorseite liest stationsbezogenen State": '/api/tents/${encodeURIComponent(TENT_ID)}/state' in sensors,
        "Sensorseite schreibt stationsbezogene Zuordnung": '/api/tents/${encodeURIComponent(TENT_ID)}/sensors/assignments' in sensors,
        "Sensor-Offsets laufen über Sensor-API": 'offsets: { [key]: value }' in sensors and "CONFIG_URL" not in sensors,
        "Sensorseite nutzt kein globales /api/state": 'fetch("/api/state' not in sensors and "fetch('/api/state" not in sensors,
        "Zentrale Sensorübersicht ist N-Stationen-fähig": 'for (const tent of tents)' in sensor_hub and 'fetch("/api/tents")' in sensor_hub,
        "Tent-Config ist jetzt schreibbar": 'methods=["GET", "POST"]' in tent_routes and '/api/tents/<tent_id>/config' in tent_routes,
        "Tent-Config schützt Sensor/Geräte/Hardware-Scope": "_STATION_CONFIG_FORBIDDEN_KEYS" in tent_routes and 'key.startswith("IP_")' in tent_routes and 'key.startswith("RELAY_")' in tent_routes,
        "Tent-Profilroute vorhanden": '/api/tents/<tent_id>/profile/<name>' in tent_routes,
        "Tent-Sensorzuweisung vorhanden": '/api/tents/<tent_id>/sensors/assignments' in sensor_routes,
        "Tent-Geräte-API vorhanden": '/api/tents/<tent_id>/devices/<device>' in device_routes,
        "Geräte-API schaltet nicht direkt Hardware": 'set_device(' not in device_routes and 'switch_shelly' not in device_routes,
        "Verlauf filtert nach tent_id": diagram_routes.count('WHERE tent_id = ? AND ts >= ?') >= 3,
        "Stations-History-Reset filtert tent_id": 'DELETE FROM temp_history WHERE tent_id = ?' in diagram_routes,
        "Generische Gerätevorlage unterstützt alle Modi": all(f'value="{mode}"' in device_template for mode in ("OFF", "ON", "TIME", "INTERVAL", "ENV")),
        "Gerätevorlage nutzt stationsbezogene API": '/api/tents/${encodeURIComponent(TENT_ID)}/devices/${encodeURIComponent(DEVICE)}' in device_template,
        "Shadow-Status bleibt sichtbar": "SHADOW" in device_template and "hardware" in device_template.lower(),
    }

    # Rechte-Regression ohne Flask-Abhängigkeit.
    spec = importlib.util.spec_from_file_location("phase4c_policy", ROOT / "auth" / "policy.py")
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)

    req = policy.permission_requirement("/grow-control/tents/tent_2/settings", "GET")
    checks["Stations-Settings benötigen settings.view"] = req.allows({"settings.view"}) and not req.allows({"grow.view"})

    req = policy.permission_requirement("/grow-control/tents/tent_2/sensors", "GET")
    checks["Stations-Sensorseite benötigt hardware.view"] = req.allows({"hardware.view"}) and not req.allows({"grow.view"})

    req = policy.permission_requirement("/api/tents/tent_2/config", "POST")
    checks["Stations-Config benötigt Konfigurationsrecht"] = (
        req.allows({"grow.configure"})
        and req.allows({"settings.manage"})
        and not req.allows({"grow.control"})
    )

    req = policy.permission_requirement("/api/tents/tent_2/sensors/assignments", "POST")
    checks["Stations-Sensorzuweisung benötigt hardware.configure"] = (
        req.allows({"hardware.configure"}) and not req.allows({"grow.configure"})
    )

    req = policy.permission_requirement("/api/tents/tent_2/devices/fan", "POST")
    checks["Stations-Gerätekonfiguration benötigt grow.configure"] = (
        req.allows({"grow.configure"}) and not req.allows({"grow.control"})
    )

    req = policy.permission_requirement("/api/tents/tent_2/history", "GET")
    checks["Stations-Historie benötigt grow.view"] = req.allows({"grow.view"})

    # Laufzeit-Isolation: Updates dürfen ausschließlich die ausgewählte Runtime
    # und deren Persistenzcallback berühren.
    from core.config_update import apply_config_patch
    from core.devices import DEVICE_NAMES, update_device_config
    from core.profile import PROFILES, apply_profile, get_active_profile
    from core.runtime import create_isolated_runtime

    saved_a = []
    saved_b = []
    rt_a = create_isolated_runtime(
        "phase4c_a",
        name="Phase4C A",
        save_config_callback=lambda cfg: saved_a.append(deepcopy(cfg)),
        shadow_enabled=True,
    )
    rt_b = create_isolated_runtime(
        "phase4c_b",
        name="Phase4C B",
        save_config_callback=lambda cfg: saved_b.append(deepcopy(cfg)),
        shadow_enabled=True,
    )

    old_b_temp = rt_b.config["DAY_TEMP"]
    apply_config_patch({"DAY_TEMP": 27.5, "TEMP_OFFSET": 0.4}, runtime=rt_a)
    checks["Config-Patch verändert nur eine Runtime"] = rt_a.config["DAY_TEMP"] == 27.5 and rt_b.config["DAY_TEMP"] == old_b_temp
    checks["Config-Patch persistiert nur ausgewählte Runtime"] = len(saved_a) == 1 and len(saved_b) == 0

    before_invalid = deepcopy(rt_a.config)
    try:
        apply_config_patch({"DAY_TEMP": 26.1, "RAMP_DURATION_MIN": "kaputt"}, runtime=rt_a)
    except ValueError:
        pass
    else:
        raise AssertionError("Ungültiger Integer wurde nicht abgelehnt")
    checks["Fehlerhafter Config-Patch bleibt atomar"] = rt_a.config == before_invalid

    update_device_config(
        "fan",
        {
            "mode": "INTERVAL",
            "params": {"interval_on": 120, "interval_off": 480},
            "env_config": {"use_temp": True, "logic": "OR", "direction": "HIGH"},
        },
        runtime=rt_b,
    )
    checks["Geräteupdate verändert nur ausgewählte Runtime"] = (
        rt_b.config["DEVICE_MODES"]["fan"] == "INTERVAL"
        and rt_a.config["DEVICE_MODES"].get("fan") != "INTERVAL"
    )
    before_bad_device = deepcopy(rt_b.config)
    try:
        update_device_config("fan", {"mode": "UNGUELTIG", "params": {"interval_on": 1}}, runtime=rt_b)
    except ValueError:
        pass
    else:
        raise AssertionError("Ungültiger Gerätemodus wurde nicht abgelehnt")
    checks["Fehlerhaftes Geräteupdate bleibt atomar"] = rt_b.config == before_bad_device
    checks["Alle bekannten Geräte teilen dieselbe Backend-Logik"] = set(DEVICE_NAMES) == {
        "heating", "fan", "light", "vent", "irrigation", "humidifier", "dehumidifier", "light2", "vent2"
    }

    # Ein Preset ist ein gemeinsamer Katalogeintrag, aber das aktive Preset und
    # die daraus kopierten Werte gehören zur jeweiligen Station.
    old_profiles = deepcopy(PROFILES)
    try:
        PROFILES.setdefault("profiles", {})["phase4c_test"] = {
            "DAY_TEMP": 25.2,
            "DAY_HUM": 61.0,
        }
        before_b = rt_b.config["DAY_TEMP"]
        require(apply_profile("phase4c_test", runtime=rt_a), "Testprofil konnte nicht angewendet werden")
        checks["Profilwerte werden nur in ausgewählte Runtime kopiert"] = rt_a.config["DAY_TEMP"] == 25.2 and rt_b.config["DAY_TEMP"] == before_b
        checks["Aktives Profil ist stationslokal"] = get_active_profile(rt_a) == "phase4c_test" and get_active_profile(rt_b) != "phase4c_test"
    finally:
        PROFILES.clear()
        PROFILES.update(old_profiles)

    failed = [name for name, ok in checks.items() if not ok]
    for name, ok in checks.items():
        print(("✅" if ok else "❌"), name)

    if failed:
        raise SystemExit("Phase 4C fehlgeschlagen: " + ", ".join(failed))

    print("✅ Phase 4C: stationsbezogene Unterseiten/APIs für beliebig viele lokale Grow-Stationen vollständig")


if __name__ == "__main__":
    main()
