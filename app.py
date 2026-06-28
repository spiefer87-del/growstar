#!/usr/bin/env python3
# =========================================
# 🌱 GROW BACKEND v3.6 Alpha – MQTT + REGELUNG + FLASK
# =========================================

import json
import time
import math
import datetime
import threading
import requests
import paho.mqtt.client as mqtt
import sqlite3
import os
from flask import Flask, request, jsonify, render_template, send_file
from db import init_db, insert_measurement, init_diary_db, init_plants_table
import presets
from collections import deque

import core.state as state
import core.context as ctx

from core.config import config, save_config

from core.helpers import (
        calculate_vpd,
        minutes_now,
        is_night,
        minute_distance,
        in_time_window,
    )

from core.ramp import (
        start_ramp,
        stop_ramp,
        update_ramp,
        get_ramped_target,
        resync_active_ramp,
        check_ramp_schedule,
        update_ramp_duration
    )

from core.profile import (
        get_profile,        
        apply_profile,
        load_profiles,
        save_profiles,
        PROFILES
    )

from core.actuators import (
            switch_shelly,
            get_shelly_relay_state,
            set_device,
            set_heating,
            set_fan,
            set_light,
            set_vent,
            set_irrigation,
            set_humidifier,
            set_dehumidifier,
            set_light2,
            set_vent2,
        )

from core.control import (
            update_temperature_setpoint,
            update_humidity_setpoint,
            control_device,
        )

from core.devices import (
            get_device_mode,
            get_device_params,
        )

from services.energy import (
            get_shelly_energy,
            refresh_energy_state,
            get_today_kwh,
            do_energy_day_reset,
        )

from services.watchdog import (
            log_event,
            watchdog_loop,
        )

from services.shelly import (
            shelly_set,
            failsafe_check,
            sync_relay,
        )

from threads.mqtt import mqtt_thread
from threads.shelly import shelly_background_loop

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

init_db()
init_diary_db()
init_plants_table()

# =========================================
# 📡 MQTT
# =========================================
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_DS = "sensor/ds18b20"
TOPIC_DHT = "sensor/dht22"




# =========================================
# 🔌 SHELLYS
# =========================================
# =========================================
# 🔌 SHELLY (4-RELAY GERÄT)
# =========================================
SENSOR_WARN = 30          # ab wann Warnung
SENSOR_TIMEOUT = 120      # ab wann stale / ungültig
DB_INTERVAL = 30          # Sekunden zwischen DB-Einträgen (5min)


# =========================================
# Globale Konstanten
# =========================================

os.makedirs("logs", exist_ok=True)




def mark_stale_sensors():
    """
    Macht Sensor-Timeouts stabil:
    - wenn stale → Werte auf None + Regelung stoppen
    - wenn wieder ok → automatisch wieder aktivieren
    """

    now = time.time()

    with ctx.state_lock:
        temp_age = now - state.last_ds_time
        hum_age = now - state.last_dht_time

    # =========================
    # 🌡️ TEMP
    # =========================

    if temp_age > SENSOR_TIMEOUT:
        # Sensor ist stale
        if not state.temp_stale:
            print(f"⚠️ TEMP SENSOR STALE ({int(temp_age)}s ohne Daten)")
        state.temp_stale = True

        state.live_state["temp"] = None
        state.live_state["temp_raw"] = None
        state.live_state["vpd"] = None

        # Sicherheitsaktion
        set_heating(False, "(TEMP SENSOR STALE)")

    else:
        # Sensor wieder ok
        if state.temp_stale:
            print("✅ TEMP SENSOR wieder da")
        state.temp_stale = False

    # =========================
    # 💧 HUM
    # =========================

    if hum_age > SENSOR_TIMEOUT:
        if not state.hum_stale:
            print(f"⚠️ HUM SENSOR STALE ({int(hum_age)}s ohne Daten)")
        state.hum_stale = True

        state.live_state["hum"] = None
        state.live_state["hum_raw"] = None
        state.live_state["vpd"] = None

        # Sicherheitsaktion
        set_fan(False, "(HUM SENSOR STALE)")

    else:
        if state.hum_stale:
            print("✅ HUM SENSOR wieder da")
        state.hum_stale = False

    # =========================
    # 🌱 VPD neu berechnen sobald beide ok
    # =========================
    if (
        state.live_state.get("temp") is not None
        and state.live_state.get("hum") is not None
    ):
        state.live_state["vpd"] = calculate_vpd(
            state.live_state["temp"],
            state.live_state["hum"]
        )






# =========================================
# 🔌 SHELLY-FUNKTIONEN
# =========================================



def control_time_mode(device):
    params = get_device_params(device)
    now_min = minutes_now()

    start = int(params.get("start_min", 0))
    end   = int(params.get("end_min", 0))

    set_device(device, in_time_window(now_min, start, end))



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
# 📡 MQTT CALLBACKS (paho-mqtt 2.x)
# =========================================

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("✅ MQTT verbunden")
        client.subscribe([(TOPIC_DS, 0), (TOPIC_DHT, 0)])

def on_message(client, userdata, msg):
    
    ctx.MQTT_LAST_MSG = time.time()


    try:
        data = json.loads(msg.payload.decode())
    except Exception as e:
        print("❌ MQTT JSON Fehler:", e)
        return

    now = time.time()

    # =========================
    # 🌡️ TEMPERATUR
    # =========================
    if msg.topic == TOPIC_DS and "temp" in data:
        try:
            temp_raw = float(data["temp"])
        except:
            return

        temp = round(temp_raw + float(config.get("TEMP_OFFSET", 0.0)), 2)

        with ctx.state_lock:
            state.last_ds_temp = temp_raw
            state.last_ds_time = now

            state.live_state["temp_raw"] = temp_raw
            state.live_state["temp"] = temp

        # Optional debug
        # print(f"🌡️ TEMP {temp:.2f}°C")

        return

    # =========================
    # 💧 HUMIDITY
    # =========================
    if msg.topic == TOPIC_DHT and "hum" in data:
        try:
            hum_raw = float(data["hum"])
        except:
            return

        hum = round(hum_raw + float(config.get("HUM_OFFSET", 0.0)), 2)

        with ctx.state_lock:
            state.last_hum = hum_raw
            state.last_dht_time = now

            state.live_state["hum_raw"] = hum_raw
            state.live_state["hum"] = hum

        # Optional debug
        # print(f"💧 HUM {hum:.2f}%")

        return
    
# =========================================
# 🧵 SHELLY + ENERGY THREAD (NON-BLOCKING MAINLOOP)
# =========================================

def shelly_background_loop():

    ENERGY_INTERVAL = 30     # Sekunden
    FAILSAFE_INTERVAL = 30   # Sekunden

    ENERGY_DEVICES = {
        "heating": ("IP_HEATING", "RELAY_HEATING"),
        "light":   ("IP_LIGHT",   "RELAY_LIGHT"),
        "fan":     ("IP_FAN",     "RELAY_FAN"),
        "vent":    ("IP_VENT",    "RELAY_VENT"),
    }

    while True:
        try:
            now = time.time()

            # =========================================
            # 🛡️ FAILSAFE (Shelly Relay Sync)
            # =========================================
            if now - ctx.last_failsafe_poll >= FAILSAFE_INTERVAL:
                ctx.last_failsafe_poll = now

                with ctx.shelly_lock:
                    failsafe_check("heating", "IP_HEATING", "RELAY_HEATING")
                    failsafe_check("fan", "IP_FAN", "RELAY_FAN")
                    failsafe_check("light", "IP_LIGHT", "RELAY_LIGHT")
                    failsafe_check("vent", "IP_VENT", "RELAY_VENT")
                    #failsafe_check("irrigation", "IP_IRRIGATION", "RELAY_IRRIGATION")
                    #failsafe_check("humidifier", "IP_HUMIDIFIER", "RELAY_HUMIDIFIER")
                    #failsafe_check("dehumidifier", "IP_DEHUMIDIFIER", "RELAY_DEHUMIDIFIER")
                    #failsafe_check("light2", "IP_LIGHT2", "RELAY_LIGHT2")
                    #failsafe_check("vent2", "IP_VENT2", "RELAY_VENT2")

            # =========================================
            # ⚡ ENERGY POLLING
            # =========================================
            if now - ctx.last_energy_poll >= ENERGY_INTERVAL:
                ctx.last_energy_poll = now

                tmp = {}

                # config sicher lesen
                with ctx.shelly_lock:
                    for name, (ip_k, r_k) in ENERGY_DEVICES.items():
                        ip = config.get(ip_k)
                        relay = config.get(r_k)

                        if not ip or relay is None:
                            continue

                        e = get_shelly_energy(ip, relay, name, timeout=2)
                        if e:
                            tmp[name] = e

                # atomar übernehmen
                with ctx.energy_lock:
                    ctx.energy_state.clear()
                    ctx.energy_state.update(tmp)

            # =========================================
            # 📅 AUTO TAGESRESET (sauber)
            # =========================================

            reset_min = int(config.get("ENERGY_DAY_RESET_MIN", 0))
            now = datetime.datetime.now()
            now_min = now.hour * 60 + now.minute
            today_key = now.date().isoformat()

            last_reset_day = config.get("ENERGY_LAST_DAY_RESET")

            # Nur wenn:
            # 1️⃣ wir NACH der Reset-Uhrzeit sind
            # 2️⃣ heute noch nicht resettet wurde
            if now_min >= reset_min and last_reset_day != today_key:

                print(f"📅 AUTO RESET ausgelöst ({now.hour:02d}:{now.minute:02d})")

                with ctx.shelly_lock:
                    do_energy_day_reset()

                # WICHTIG: Sofort merken, dass wir heute resettet haben
                config["ENERGY_LAST_DAY_RESET"] = today_key
                save_config(config)




        except Exception as e:
            print("❌ Shelly Background Thread Fehler:", e)

        time.sleep(1)
    


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

print("🌱 Grow-Backend läuft")

# =========================================
# 🛡️ FAILSAFE LOOP (Main)
# =========================================
try:
    while True:
        now = time.time()

        # =========================================
        # 🎯 Sollwerte aktualisieren (immer, auch ohne Sensorwerte
        # =========================================
        update_temperature_setpoint()
        update_humidity_setpoint()
        check_ramp_schedule()
        # =========================================
        # 🔁 Rampen-Sollwert regelmäßig aktualisieren
        # =========================================
        if state.ramp_active:
            update_ramp()
        
        # =========================================
        # 🧊 SENSOR STALE LOGIK (niemals blockieren)
        # =========================================
        mark_stale_sensors()

        # Snapshot (threadsafe)
        with ctx.state_lock:
            temp_val = state.live_state.get("temp")
            hum_val = state.live_state.get("hum")

        # =========================================
        # 📊 VPD + DB Logging (entkoppelt von MQTT)
        # =========================================
        if now - state.last_db_write >= DB_INTERVAL:
            state.last_db_write = now

            with ctx.state_lock:

                # Targets können None sein, ist OK
                tt = state.live_state.get("temp_target")
                ht = state.live_state.get("hum_target")

            if temp_val is not None and hum_val is not None:
                vpd = calculate_vpd(temp_val, hum_val)

                with ctx.state_lock:
                    state.live_state["vpd"] = vpd

                try:
                    insert_measurement(
                        temp=temp_val,
                        temp_target=tt,
                        hum=hum_val,
                        hum_target=ht,
                        vpd=vpd
                    )
                except Exception as e:
                    print("❌ DB insert_measurement Fehler:", e)


        # =========================================
        # 🌡️ Regelung (nur wenn Werte existieren)
        # =========================================
    


        # =========================================
        # 💡 Licht + Ventilator laufen unabhängig
        # =========================================
        control_device("fan")
        control_device("vent")
        control_device("heating")
        control_device("light")


        # =========================================
        # 🛡️ SHELLY FAILSAFE (korrigiert manuelle Eingriffe)
        # =========================================
        

        time.sleep(2)

finally:
    print("\n🛑 Programm beendet – Aktoren AUS")
    set_heating(False, "(Shutdown)")
    set_fan(False, "(Shutdown)")
    set_vent(False, "(Shutdown)")
    # set_light(False, "(Shutdown)")


