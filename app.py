#!/usr/bin/env python3
# =========================================
# 🌱 GROW BACKEND v3.6 Alpha – MQTT + REGELUNG + FLASK
# Gunicorn-kompatible Fassung
# =========================================

import atexit
import os
import threading
import secrets

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from db import init_db, init_diary_db, init_plants_table
from core.config import config
from core.actuators import set_heating, set_fan, set_vent

from services.watchdog import log_event, watchdog_loop
from services.shelly import sync_relay

from threads.mqtt import mqtt_thread
from threads.shelly import shelly_background_loop
from threads.main import main_loop
from threads.hardware import hardware_loop
from threads.blu import start_blu_thread

from routes.dashboard import register as register_dashboard_routes
from routes.plant_management import register as register_plant_management_routes
from routes.state import register as register_state_routes
from routes.plants import register as register_plants_routes
from routes.diary import register as register_diary_routes
from routes.diagrams import register as register_diagrams_routes
from routes.energy import register as register_energy_routes
from routes.device import register as register_device_routes
from routes.config import register as register_config_routes
from routes.profile import register as register_profile_routes
from routes.watchdog import register as register_watchdog_routes
from routes.hardware import register as register_hardware_routes
from routes.sensors import register as register_sensor_routes
from routes.auth import register as register_auth_routes
from routes.admin import register as register_admin_routes

from auth.database import init_auth_db
from auth.middleware import install_auth


# =========================================
# Flask-Anwendung
# =========================================

def _load_or_create_secret_key():
    """Lädt einen persistenten Flask-Session-Schlüssel außerhalb des Quellcodes."""

    env_key = os.getenv("GROWSTAR_SECRET_KEY")
    if env_key:
        return env_key

    instance_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance")
    secret_file = os.path.join(instance_dir, "secret.key")
    os.makedirs(instance_dir, exist_ok=True)

    if os.path.exists(secret_file):
        with open(secret_file, "r", encoding="utf-8") as f:
            return f.read().strip()

    secret = secrets.token_hex(32)
    with open(secret_file, "w", encoding="utf-8") as f:
        f.write(secret)
    os.chmod(secret_file, 0o600)
    return secret


def create_flask_app():
    """Erzeugt die Flask-App, ohne Regelungs-Threads zu starten."""

    os.makedirs("logs", exist_ok=True)

    # Die Initialisierung bleibt vor der Routenregistrierung, wie bisher.
    init_db()
    init_diary_db()
    init_plants_table()
    init_auth_db()

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=_load_or_create_secret_key(),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Erst auf 1 setzen, wenn ausschließlich HTTPS verwendet wird.
        SESSION_COOKIE_SECURE=os.getenv("GROWSTAR_HTTPS_ONLY") == "1",
    )

    register_auth_routes(app)
    register_admin_routes(app)
    register_dashboard_routes(app)
    register_plant_management_routes(app)
    register_state_routes(app)
    register_plants_routes(app)
    register_diary_routes(app)
    register_diagrams_routes(app)
    register_energy_routes(app)
    register_device_routes(app)
    register_config_routes(app)
    register_profile_routes(app)
    register_watchdog_routes(app)
    register_hardware_routes(app)
    register_sensor_routes(app)

    # Standardmäßig ist die gesamte Oberfläche nur nach Login erreichbar.
    install_auth(app)

    # Nur aktivieren, wenn wirklich genau ein vertrauenswürdiger Reverse Proxy
    # vor Flask/Gunicorn steht.
    if os.getenv("GROWSTAR_BEHIND_PROXY") == "1":
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=1,
            x_proto=1,
            x_host=1,
        )

    return app


flask_app = create_flask_app()


# =========================================
# Growstar-Hintergrunddienste
# =========================================

_backend_lock = threading.Lock()
_backend_started = False


def _start_daemon_thread(name, target):
    thread = threading.Thread(
        name=name,
        target=target,
        daemon=True,
    )
    thread.start()
    return thread


def _sync_all_relays():
    sync_relay(
        "🔥 Heizung",
        config["IP_HEATING"],
        config["RELAY_HEATING"],
        "heating_on",
        "heating",
    )
    sync_relay(
        "💨 Lüfter",
        config["IP_FAN"],
        config["RELAY_FAN"],
        "fan_on",
        "fan",
    )
    sync_relay(
        "💡 Licht",
        config["IP_LIGHT"],
        config["RELAY_LIGHT"],
        "light_on",
        "light",
    )
    sync_relay(
        "🌀 Ventilator",
        config["IP_VENT"],
        config["RELAY_VENT"],
        "vent_on",
        "vent",
    )
    sync_relay(
        "🚿 Bewässerung",
        config["IP_IRRIGATION"],
        config["RELAY_IRRIGATION"],
        "irrigation_on",
        "irrigation",
    )
    sync_relay(
        "💧 Luftbefeuchter",
        config["IP_HUMIDIFIER"],
        config["RELAY_HUMIDIFIER"],
        "humidifier_on",
        "humidifier",
    )
    sync_relay(
        "🌵 Luftentfeuchter",
        config["IP_DEHUMIDIFIER"],
        config["RELAY_DEHUMIDIFIER"],
        "dehumidifier_on",
        "dehumidifier",
    )
    sync_relay(
        "💡 Licht 2",
        config["IP_LIGHT2"],
        config["RELAY_LIGHT2"],
        "light2_on",
        "light2",
    )
    sync_relay(
        "🌀 Ventilator 2",
        config["IP_VENT2"],
        config["RELAY_VENT2"],
        "vent2_on",
        "vent2",
    )


def start_backend():
    """Startet Hardware und Regelung genau einmal pro Prozess."""

    global _backend_started

    with _backend_lock:
        if _backend_started:
            print("ℹ️ Grow-Backend läuft bereits")
            return

        print("🌱 Grow-Backend wird gestartet")

        try:
            _sync_all_relays()

            _start_daemon_thread(
                "growstar-shelly",
                shelly_background_loop,
            )
            print("🧵 Shelly Background Thread gestartet")

            _start_daemon_thread(
                "growstar-mqtt",
                mqtt_thread,
            )
            print("📡 MQTT Sensor Thread läuft")

            _start_daemon_thread(
                "growstar-blu",
                start_blu_thread,
            )
            print("📡 BLU Sensor Thread läuft")

            _start_daemon_thread(
                "growstar-watchdog",
                watchdog_loop,
            )
            log_event("Watchdog Thread gestartet")

            _start_daemon_thread(
                "growstar-main-control",
                main_loop,
            )
            print("🧠 Main Control Thread gestartet")

            _start_daemon_thread(
                "growstar-hardware",
                hardware_loop,
            )
            print("🧠 Hardware Thread gestartet")

            _backend_started = True
            print("✅ Grow-Backend läuft")

        except Exception:
            _backend_started = False
            print("❌ Grow-Backend konnte nicht vollständig starten")
            raise


def shutdown_backend():
    """Führt beim geordneten Prozessende den bisherigen Not-Aus aus."""

    global _backend_started

    with _backend_lock:
        if not _backend_started:
            return

        _backend_started = False
        print("🛑 Grow-Backend wird beendet")

        for action in (
            lambda: set_heating(False, "(Shutdown)"),
            lambda: set_fan(False, "(Shutdown)"),
            lambda: set_vent(False, "(Shutdown)"),
        ):
            try:
                action()
            except Exception as exc:
                print(f"⚠️ Fehler beim Shutdown: {exc}")


atexit.register(shutdown_backend)


# =========================================
# Direkter Start nur für lokale Entwicklung
# =========================================

if __name__ == "__main__":
    start_backend()

    try:
        flask_app.run(
            host="0.0.0.0",
            port=5000,
            debug=False,
        )
    finally:
        shutdown_backend()
