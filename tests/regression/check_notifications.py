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

    class FakeRuntime:
        config = {
            "MIN_TEMP": 12.0,
            "MAX_TEMP": 30.0,
            "MAX_HUM": 75.0,
        }

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

    print(f"✅ Growstar Alarm & Notifications vollständig · aktuell {release.GROWSTAR_VERSION} / Phase {release.GROWSTAR_INTERNAL_PHASE}")


if __name__ == "__main__":
    main()
