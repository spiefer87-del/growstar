#!/usr/bin/env python3
# =========================================
# 🌱 GROW BACKEND – MQTT + REGELUNG + FLASK
# Gunicorn-kompatible Fassung
# Die laufende Version kommt ausschließlich aus core.release.
# =========================================

import atexit
import os
import threading
import secrets

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from db import init_db, init_diary_db, init_plants_table
from core.tents import init_tents
from core.runtime import (
    get_default_runtime,
    init_runtimes,
    list_runtimes,
    resolve_runtime,
)
from core.hardware_assignments import DEVICE_HARDWARE, device_display_label
from core.release import GROWSTAR_VERSION

from services.watchdog import log_event, watchdog_loop
from services.shelly import sync_relay

from threads.mqtt import mqtt_thread
from threads.shelly import shelly_background_loop
from threads.main import main_loop
from threads.hardware import hardware_loop
from threads.blu import start_blu_thread
from services.hardware_recovery import start_hardware_recovery_thread
from services.live_control import live_arming_loop
from services.restart_policy import apply_shutdown_restart_policy

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
from routes.tents import register as register_tent_routes
from routes.auth import register as register_auth_routes
from routes.admin import register as register_admin_routes
from routes.release import register as register_release_routes
from routes.restart_policy import register as register_restart_policy_routes

from auth.database import init_auth_db
from auth.middleware import install_auth
from plant_management.database import init_plant_management_db
from plant_management.journal import init_plant_journal_db
from plant_management.propagation import init_propagation_db


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
    # Phase 1 Multi-Zelt: bestehende Installation wird als tent_1 registriert.
    init_tents()
    init_runtimes()
    init_db()
    init_diary_db()
    init_plants_table()
    init_auth_db()
    init_plant_management_db()
    init_propagation_db()
    init_plant_journal_db()

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=_load_or_create_secret_key(),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        GROWSTAR_VERSION=GROWSTAR_VERSION,
        # Erst auf 1 setzen, wenn ausschließlich HTTPS verwendet wird.
        SESSION_COOKIE_SECURE=os.getenv("GROWSTAR_HTTPS_ONLY") == "1",
    )

    register_auth_routes(app)
    register_admin_routes(app)
    register_release_routes(app)
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
    register_tent_routes(app)
    register_restart_policy_routes(app)

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


def _sync_all_relays(runtime=None):
    """Seedet vor dem Thread-Start jeden zugeordneten Aktor aus der Hardware.

    Das ist für RESTART_POLICY=KEEP entscheidend: Growstar übernimmt den
    physischen Zustand, bevor Failsafe oder Regelkreis irgendeinen Soll/Ist-
    Vergleich durchführen. Phase 4T bezieht dabei erstmals auch AUX1..AUX4 ein.
    """

    rt = resolve_runtime(runtime)
    cfg = rt.config

    for device, meta in DEVICE_HARDWARE.items():
        ip = cfg.get(meta["ip_key"])
        relay = cfg.get(meta["relay_key"])

        if not ip or relay is None:
            continue

        label = (
            f"{meta.get('icon') or ''} "
            f"{device_display_label(cfg, device)}"
        ).strip()

        sync_relay(
            label,
            ip,
            relay,
            f"{device}_on",
            device,
            runtime=rt,
        )


def start_backend():
    """Startet Hardware und Regelung genau einmal pro Prozess."""

    global _backend_started

    with _backend_lock:
        if _backend_started:
            print("ℹ️ Grow-Backend läuft bereits")
            return

        print(f"🌱 Growstar v{GROWSTAR_VERSION} Backend wird gestartet")

        runtime = get_default_runtime()

        try:
            _sync_all_relays(runtime=runtime)

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
                lambda: main_loop(runtime=runtime, shadow=False),
            )
            print("🧠 Main Control Thread gestartet")

            # Phase 4H: jede zusätzliche aktive Station besitzt weiterhin genau
            # EINEN Regelkreis-Thread. Shadow und ARMING starten hardwaregesperrt;
            # nach erfolgreichem Preflight kann derselbe Thread dynamisch LIVE
            # werden. Inaktive Stationen bekommen weiterhin keinen Thread.
            for extra_runtime in list_runtimes():
                if extra_runtime.tent_id == runtime.tent_id:
                    continue
                if not extra_runtime.enabled:
                    continue
                if not (extra_runtime.shadow_enabled or extra_runtime.live_requested):
                    continue

                _start_daemon_thread(
                    f"growstar-control-{extra_runtime.tent_id}",
                    lambda rt=extra_runtime: main_loop(
                        runtime=rt,
                        shadow=None,
                    ),
                )

                if extra_runtime.live_requested:
                    print(
                        f"🟠 [{extra_runtime.tent_id}] "
                        "ARMING Control Thread gestartet"
                    )
                else:
                    print(
                        f"🧪 [{extra_runtime.tent_id}] "
                        "Shadow Control Thread gestartet"
                    )

            _start_daemon_thread(
                "growstar-hardware",
                hardware_loop,
            )
            print("🧠 Hardware Thread gestartet")

            # The arming thread only consumes runtime state + the read-only
            # actuator-health cache. Starting it after hardware_loop ensures
            # that persisted LIVE stations cannot open their gate before the
            # central hardware poll has produced a fresh result.
            _start_daemon_thread(
                "growstar-live-arming",
                live_arming_loop,
            )
            print("🟠 LIVE-Arming Thread gestartet")

            # Phase 4F: bekannte Gateways/BLE-Sensoren nach Neustart
            # automatisch wiederherstellen. Der Recovery-Thread arbeitet
            # vollständig parallel; er blockiert den Regelungsstart nicht.
            start_hardware_recovery_thread()
            print("♻️ Hardware Auto-Recovery Thread gestartet")

            _backend_started = True
            print("✅ Grow-Backend läuft")

        except Exception:
            _backend_started = False
            print("❌ Grow-Backend konnte nicht vollständig starten")
            raise


def shutdown_backend():
    """Wendet beim geordneten Prozessende die stationsbezogene Restart-Policy an."""

    global _backend_started

    with _backend_lock:
        if not _backend_started:
            return

        _backend_started = False
        print("🛑 Grow-Backend wird beendet")

        for runtime in list_runtimes():
            if not runtime.control_enabled:
                continue

            # Controller-/Safety-Threads dürfen während des Shutdowns nicht
            # gegen die explizite Restart-Policy arbeiten.
            runtime.disarming = True

            try:
                result = apply_shutdown_restart_policy(
                    runtime,
                    verify=True,
                )
            except Exception as exc:
                print(
                    f"⚠️ [{runtime.tent_id}] Restart-Policy fehlgeschlagen:",
                    exc,
                )
                continue

            for item in result.get("devices", {}).values():
                if not item.get("configured"):
                    continue

                if item.get("action") == "KEEP":
                    print(
                        f"↔️ [{runtime.tent_id}] "
                        f"{item.get('label')}: Zustand beibehalten"
                    )
                elif item.get("error"):
                    print(
                        f"⚠️ [{runtime.tent_id}] "
                        f"{item.get('label')}: {item.get('error')}"
                    )
                else:
                    print(
                        f"🛑 [{runtime.tent_id}] "
                        f"{item.get('label')}: sicher AUS"
                    )


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
