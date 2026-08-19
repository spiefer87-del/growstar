#!/usr/bin/env python3
"""Growstar – Alarm- und Telegram-Regressionstest (Feature seit 3.9.0 / 4V)."""

from pathlib import Path
import ast
import importlib.util
import os
import sys
import tempfile
import types


ROOT = Path(__file__).resolve().parents[2]


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


def install_alert_stubs():
    runtime = types.ModuleType("core.runtime")

    class FakeState:
        live_state = {
            "temp_target": 20.0,
            "hum_target": 60.0,
        }

    class FakeRuntime:
        config = {
            "MIN_TEMP": 12.0,
            "MAX_TEMP": 30.0,
            "MIN_HUM": 30.0,
            "MAX_HUM": 80.0,
            "TEMP_ALERT_TOL": 5.0,
            "HUM_ALERT_TOL": 10.0,
        }
        state = FakeState()

    runtime.get_runtime = lambda tent_id: FakeRuntime()
    sys.modules["core.runtime"] = runtime

    health = types.ModuleType("core.watchdog_health")
    health.build_watchdog_snapshot = lambda: {}
    sys.modules["core.watchdog_health"] = health

    settings = types.ModuleType("services.notification_settings")
    settings.load_notification_settings = lambda: {
        "telegram": {"enabled": False},
        "rules": {},
    }
    sys.modules["services.notification_settings"] = settings

    notifications = types.ModuleType("services.notifications")
    notifications.enqueue_notification = lambda *args, **kwargs: True
    sys.modules["services.notifications"] = notifications


def main():
    for rel in (
        "app.py",
        "core/release.py",
        "core/config.py",
        "core/environment_limits.py",
        "core/config_update.py",
        "services/telegram.py",
        "services/notification_settings.py",
        "services/notifications.py",
        "services/alerts.py",
        "routes/notifications.py",
        "tests/regression/check_notifications.py",
    ):
        ast.parse(read(rel), filename=rel)
        print("✅ Python-Syntax", rel)

    release = load_module("growstar_notifications_release", "core/release.py")
    feature_release = next(
        (
            item
            for item in release.RELEASES
            if item.get("version") == "3.9.0"
            and item.get("phase") == "4V"
        ),
        None,
    )
    require(
        feature_release is not None,
        "Feature-Release 3.9.0 / Phase 4V bleibt in den Patch Notes dokumentiert",
    )

    thresholds_release = next(
        (
            item
            for item in release.RELEASES
            if item.get("version") == "3.9.2"
            and item.get("phase") == "4V.2"
        ),
        None,
    )
    require(
        thresholds_release is not None,
        "Feature-Release 3.9.2 / Phase 4V.2 ist in den Patch Notes dokumentiert",
    )

    env_limits = load_module(
        "growstar_environment_limits",
        "core/environment_limits.py",
    )
    valid_limits = env_limits.validate_environment_limits({
        "MIN_TEMP": 12.0,
        "MAX_TEMP": 30.0,
        "MIN_HUM": 30.0,
        "MAX_HUM": 80.0,
        "TEMP_ALERT_TOL": 5.0,
        "HUM_ALERT_TOL": 10.0,
        "DAY_TEMP_TOL": 2.0,
        "NIGHT_TEMP_TOL": 2.0,
        "DAY_HUM_TOL": 5.0,
        "NIGHT_HUM_TOL": 5.0,
    })
    require(
        valid_limits["temp_alert_tol"] == 5.0
        and valid_limits["hum_alert_tol"] == 10.0,
        "Getrennte Temperatur-/Feuchte-Alarmtoleranzen werden validiert",
    )

    try:
        env_limits.validate_environment_limits({
            "MIN_TEMP": 30.0,
            "MAX_TEMP": 20.0,
            "MIN_HUM": 30.0,
            "MAX_HUM": 80.0,
            "TEMP_ALERT_TOL": 5.0,
            "HUM_ALERT_TOL": 10.0,
            "DAY_TEMP_TOL": 2.0,
            "NIGHT_TEMP_TOL": 2.0,
            "DAY_HUM_TOL": 5.0,
            "NIGHT_HUM_TOL": 5.0,
        })
    except ValueError:
        pass
    else:
        raise AssertionError("Ungültige MIN_TEMP/MAX_TEMP-Kombination wurde akzeptiert")
    print("✅ Ungültige absolute Temperaturgrenzen werden blockiert")

    telegram = load_module("growstar_390_telegram", "services/telegram.py")
    require(
        telegram.validate_token_format(
            "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcd"
        ).startswith("123456789:"),
        "Telegram Bot-Token-Format wird akzeptiert",
    )
    try:
        telegram.validate_token_format("ungültig token")
    except ValueError:
        pass
    else:
        raise AssertionError("Ungültiger Telegram-Token wurde akzeptiert")
    print("✅ Ungültige Telegram-Tokens werden blockiert")

    telegram_source = read("services/telegram.py")
    require(
        "https://api.telegram.org" in telegram_source
        and "shell=True" not in telegram_source
        and "subprocess" not in telegram_source,
        "Telegram-Client verwendet HTTPS ohne Shell-/Subprocess-Ausführung",
    )

    settings = load_module(
        "growstar_390_settings",
        "services/notification_settings.py",
    )
    with tempfile.TemporaryDirectory() as tmp:
        settings.INSTANCE_DIR = Path(tmp)
        settings.SETTINGS_FILE = Path(tmp) / "notifications.json"

        settings.save_bot_connection(
            "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcd",
            {
                "id": 1,
                "username": "growstar_test_bot",
                "first_name": "Growstar Test",
            },
        )

        public = settings.public_notification_settings()
        raw = settings.load_notification_settings()

        require(
            public["telegram"]["token_configured"] is True
            and "bot_token" not in public["telegram"],
            "Öffentliche Einstellungen geben den Bot-Token niemals zurück",
        )
        require(
            raw["telegram"]["bot_token"].startswith("123456789:"),
            "Bot-Token wird intern lokal gespeichert",
        )
        mode = os.stat(settings.SETTINGS_FILE).st_mode & 0o777
        require(
            mode == 0o600,
            "Lokale notifications.json wird mit Dateimodus 0600 gespeichert",
        )

    install_alert_stubs()
    alerts = load_module("growstar_390_alerts", "services/alerts.py")

    base_station = {
        "id": "tent_1",
        "name": "Zelt 1",
        "enabled": True,
        "loop": {"stale": False},
        "temperature": {
            "configured": True,
            "stale": False,
            "value": 24.0,
            "source_id": "mqtt:pico_01",
        },
        "humidity": {
            "configured": True,
            "stale": False,
            "value": 55.0,
            "source_id": "mqtt:pico_01",
        },
        "config": {"ok": True, "issues": []},
        "hardware": {"endpoints": []},
        "safety": {"stale": False, "active": False},
    }

    stale = dict(base_station)
    stale["temperature"] = dict(base_station["temperature"])
    stale["temperature"].update({"stale": True, "age": 130})
    candidates = alerts.extract_alarm_candidates({
        "stations": [stale],
        "controller": {"threads": {}, "mqtt": {"stale": False}},
    })
    require(
        "station:tent_1:sensor:temperature:stale" in candidates,
        "Stale Temperatursensor erzeugt stabilen Alarm-Key",
    )

    within_alert_band = dict(base_station)
    within_alert_band["temperature"] = dict(base_station["temperature"])
    within_alert_band["temperature"]["value"] = 24.9
    candidates = alerts.extract_alarm_candidates({
        "stations": [within_alert_band],
        "controller": {"threads": {}, "mqtt": {"stale": False}},
    })
    require(
        "station:tent_1:sensor:temperature:limit" not in candidates,
        "20 °C Soll mit ±5 °C Alarmtoleranz alarmiert bei 24.9 °C noch nicht",
    )

    relative_high = dict(base_station)
    relative_high["temperature"] = dict(base_station["temperature"])
    relative_high["temperature"]["value"] = 25.0
    candidates = alerts.extract_alarm_candidates({
        "stations": [relative_high],
        "controller": {"threads": {}, "mqtt": {"stale": False}},
    })
    relative_item = candidates.get("station:tent_1:sensor:temperature:limit")
    require(
        relative_item is not None
        and relative_item["severity"] == "error"
        and "Alarmtoleranz ±5.0 °C" in relative_item["detail"],
        "20 °C Soll mit ±5 °C Alarmtoleranz alarmiert ab 25.0 °C",
    )

    hum_relative_high = dict(base_station)
    hum_relative_high["humidity"] = dict(base_station["humidity"])
    hum_relative_high["humidity"]["value"] = 70.0
    candidates = alerts.extract_alarm_candidates({
        "stations": [hum_relative_high],
        "controller": {"threads": {}, "mqtt": {"stale": False}},
    })
    hum_item = candidates.get("station:tent_1:sensor:humidity:limit")
    require(
        hum_item is not None
        and hum_item["severity"] == "error"
        and "Alarmtoleranz ±10.0 %" in hum_item["detail"],
        "60 % Soll mit ±10 % Alarmtoleranz alarmiert ab 70 %",
    )

    high = dict(base_station)
    high["temperature"] = dict(base_station["temperature"])
    high["temperature"]["value"] = 31.5
    candidates = alerts.extract_alarm_candidates({
        "stations": [high],
        "controller": {"threads": {}, "mqtt": {"stale": False}},
    })
    item = candidates.get("station:tent_1:sensor:temperature:limit")
    require(
        item is not None
        and item["severity"] == "critical"
        and item["rule"] == "sensor_limits",
        "Temperatur über MAX_TEMP erzeugt critical sensor_limits Alarm",
    )

    hw = dict(base_station)
    hw["hardware"] = {
        "endpoints": [{
            "device": "heating",
            "label": "Heizung",
            "ip": "192.0.2.10",
            "relay": 0,
            "state": "error",
            "consecutive_failures": 1,
            "last_error": "timeout",
        }]
    }
    candidates = alerts.extract_alarm_candidates({
        "stations": [hw],
        "controller": {"threads": {}, "mqtt": {"stale": False}},
    })
    require(
        not any(":hardware:" in key for key in candidates),
        "Ein einzelner Hardwarefehler erzeugt noch keinen Alarm",
    )

    hw["hardware"]["endpoints"][0]["consecutive_failures"] = 2
    candidates = alerts.extract_alarm_candidates({
        "stations": [hw],
        "controller": {"threads": {}, "mqtt": {"stale": False}},
    })
    require(
        any(":hardware:" in key for key in candidates),
        "Ab zwei Hardwarefehlern wird ein Aktoralarm erzeugt",
    )

    alert_source = read("services/alerts.py")
    require(
        "core.actuators" not in alert_source
        and "switch_shelly" not in alert_source
        and "set_device" not in alert_source,
        "Alarm-Engine besitzt keinen Aktor-Schaltpfad",
    )
    require(
        "STARTUP_GRACE_SEC = 90" in alert_source
        and "last_notified_at" in alert_source
        and "recovered" in alert_source,
        "Alarm-Engine enthält Startschutz, Deduplizierung und Entwarnung",
    )

    app = read("app.py")
    require(
        "register_notification_routes(app)" in app
        and '"growstar-notifications"' in app
        and '"growstar-alerts"' in app,
        "App registriert Notification-Routen und getrennte Worker-Threads",
    )

    routes = read("routes/notifications.py")
    require(
        '@permission_required("settings.view")' in routes
        and '@permission_required("settings.manage")' in routes,
        "Notification-Routen verwenden settings.view/settings.manage",
    )

    dashboard = read("templates/grow_control_dashboard.html")
    require(
        "Alarm & Benachrichtigungen" in dashboard
        and "growstar_notifications_page" in dashboard,
        "Grow-Control-Dashboard enthält die Notification-Kachel",
    )

    template = read("templates/notifications.html")
    require(
        "Bot verbinden" in template
        and "Chat finden" in template
        and "Testnachricht senden" in template,
        "Benachrichtigungsseite enthält den vollständigen Telegram-Setupfluss",
    )

    climate_template = read("templates/settings.html")
    require(
        "TEMP_ALERT_TOL" in climate_template
        and "HUM_ALERT_TOL" in climate_template
        and "MIN_HUM" in climate_template
        and "MAX_HUM" in climate_template,
        "Stations-Setup enthält Alarmtoleranzen sowie MIN/MAX-Grenzen",
    )
    require(
        "Regel-Toleranz" in climate_template
        and "Alarm-Toleranz" in climate_template
        and "Absolute Schutzgrenze" in climate_template,
        "Setup erklärt die drei Ebenen Sollwert, Regelung und Alarm",
    )

    require(
        'id="lighting-duration"' in climate_template
        and "Beleuchtungsdauer" in climate_template
        and "updateLightingDuration" in climate_template,
        "Zeit-Kachel zeigt die automatisch berechnete Beleuchtungsdauer",
    )
    require(
        "(nightStart - dayStart + 1440) % 1440" in climate_template
        and '["DAY_START_TIME","NIGHT_START_TIME"]' in climate_template,
        "Beleuchtungsdauer berücksichtigt Mitternacht und aktualisiert sich bei Zeitänderungen",
    )
    require(
        'hours === 1 ? "Stunde" : "Stunden"' in climate_template,
        "Volle Beleuchtungsstunden werden verständlich als Stunden angezeigt",
    )

    setup_template = read("templates/grow_control_setup.html")
    require(
        "Klima & Grenzwerte" in setup_template
        and "/grow-control/tents/${encodeURIComponent(t.id)}/settings" in setup_template,
        "Grow-Control-Setup verlinkt jede Station direkt zu Klima & Grenzwerte",
    )

    notification_template = read("templates/notifications.html")
    require(
        "Sensorabweichung & Grenzwerte" in notification_template,
        "Notification-Regel beschreibt relative Abweichung und absolute Grenzen",
    )

    config_source = read("core/config.py")
    require(
        '"TEMP_ALERT_TOL": 5.0' in config_source
        and '"HUM_ALERT_TOL": 10.0' in config_source
        and '"MIN_HUM": 0.0' in config_source,
        "Sichere rückwärtskompatible Alarm-Defaults sind definiert",
    )

    config_update_source = read("core/config_update.py")
    require(
        "validate_environment_limits(working)" in config_update_source,
        "Config-Updates validieren Klima-/Alarmgrenzen atomar vor dem Commit",
    )

    print(f"✅ Growstar Alarm & Notifications vollständig · aktuell {release.GROWSTAR_VERSION} / Phase {release.GROWSTAR_INTERNAL_PHASE}")


if __name__ == "__main__":
    main()
