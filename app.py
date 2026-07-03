#!/usr/bin/env python3
# =========================================
# 🌱 GROW BACKEND v3.6 Alpha – MQTT + REGELUNG + FLASK
# =========================================

import time

import threading
import os
from flask import Flask
from db import init_db, init_diary_db, init_plants_table

from core.config import config

from core.actuators import (
    set_heating,
    set_fan,
    set_vent,
)

from services.watchdog import (
            log_event,
            watchdog_loop,
        )

from services.shelly import sync_relay

from threads.mqtt import mqtt_thread
from threads.shelly import shelly_background_loop
from threads.main import main_loop

from routes.dashboard import register as register_dashboard_routes
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

init_db()
init_diary_db()
init_plants_table()


# =========================================
# Globale Konstanten
# =========================================

os.makedirs("logs", exist_ok=True)

# =========================================
# 🔌 SHELLY-FUNKTIONEN
# =========================================

sync_relay("🔥 Heizung", config["IP_HEATING"], config["RELAY_HEATING"], "heating_on", "heating")
sync_relay("💨 Lüfter",  config["IP_FAN"],     config["RELAY_FAN"],     "fan_on",     "fan")
sync_relay("💡 Licht",   config["IP_LIGHT"],   config["RELAY_LIGHT"],   "light_on",   "light")
sync_relay("🌀 Ventilator", config["IP_VENT"],  config["RELAY_VENT"],    "vent_on",    "vent")
sync_relay("🚿 Bewässerung", config["IP_IRRIGATION"], config["RELAY_IRRIGATION"], "irrigation_on", "irrigation")
sync_relay("💧 Luftbefeuchter", config["IP_HUMIDIFIER"], config["RELAY_HUMIDIFIER"], "humidifier_on", "humidifier")
sync_relay("🌵 Luftentfeuchter", config["IP_DEHUMIDIFIER"], config["RELAY_DEHUMIDIFIER"], "dehumidifier_on", "dehumidifier")
sync_relay("💡 Licht 2", config["IP_LIGHT2"], config["RELAY_LIGHT2"], "light2_on", "light2")
sync_relay("🌀 Ventilator 2", config["IP_VENT2"], config["RELAY_VENT2"], "vent2_on", "vent2")

    
# =========================================
# 🌐 FLASK WEB-UI
# =========================================
flask_app = Flask(__name__)

register_dashboard_routes(flask_app)
register_state_routes(flask_app)
register_plants_routes(flask_app)
register_diary_routes(flask_app)
register_diagrams_routes(flask_app)
register_energy_routes(flask_app)
register_device_routes(flask_app)
register_config_routes(flask_app)
register_profile_routes(flask_app)
register_watchdog_routes(flask_app)
register_hardware_routes(flask_app)



def run_flask():
    flask_app.run(host="0.0.0.0", port=5000, debug=False)


threading.Thread(target=run_flask, daemon=True).start()
print("🌐 Flask Webserver gestartet")
threading.Thread(target=shelly_background_loop, daemon=True).start()
print("🧵 Shelly Background Thread gestartet")
threading.Thread(target=mqtt_thread, daemon=True).start()
print("📡 MQTT Sensor Thread läuft")
threading.Thread(target=watchdog_loop, daemon=True).start()
log_event("Watchdog Thread gestartet")
threading.Thread(target=main_loop, daemon=True).start()
print("🧠 Main Control Thread gestartet")

print("🌱 Grow-Backend läuft")

try:

    while True:
        time.sleep(60)

finally:

    print("🛑 Programm beendet")

    set_heating(False, "(Shutdown)")
    set_fan(False, "(Shutdown)")
    set_vent(False, "(Shutdown)")
