#!/usr/bin/env python3
# =========================================
# 🌱 GROW BACKEND v3.5 Alpha – MQTT + REGELUNG + FLASK
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
from core.config import config
from core.helpers import *
from core.ramp import (
        start_ramp,
        stop_ramp,
        update_ramp,
        get_ramped_target,
        resync_active_ramp,
        update_ramp_duration
    )

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
# 🧵 THREAD STATE
# =========================================
energy_state = {}
energy_lock = threading.Lock()

shelly_lock = threading.Lock()

state_lock = threading.Lock()

last_energy_poll = 0
last_failsafe_poll = 0


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
LOG_FILE = "logs/infolog.txt"
os.makedirs("logs", exist_ok=True)

MQTT_LAST_MSG = 0   # timestamp letzter MQTT callback



def sensor_ok(last_time):
    return (time.time() - last_time) <= SENSOR_TIMEOUT

def mark_stale_sensors():
    """
    Macht Sensor-Timeouts stabil:
    - wenn stale → Werte auf None + Regelung stoppen
    - wenn wieder ok → automatisch wieder aktivieren
    """
    global temp_stale, hum_stale

    now = time.time()

    # =========================
    # 🌡️ TEMP
    # =========================
    temp_age = now - last_ds_time

    if temp_age > SENSOR_TIMEOUT:
        # Sensor ist stale
        if not temp_stale:
            print(f"⚠️ TEMP SENSOR STALE ({int(temp_age)}s ohne Daten)")
        temp_stale = True

        state.live_state["temp"] = None
        state.live_state["temp_raw"] = None
        state.live_state["vpd"] = None

        # Sicherheitsaktion
        set_heating(False, "(TEMP SENSOR STALE)")

    else:
        # Sensor wieder ok
        if temp_stale:
            print("✅ TEMP SENSOR wieder da")
        temp_stale = False

    # =========================
    # 💧 HUM
    # =========================
    hum_age = now - last_dht_time

    if hum_age > SENSOR_TIMEOUT:
        if not hum_stale:
            print(f"⚠️ HUM SENSOR STALE ({int(hum_age)}s ohne Daten)")
        hum_stale = True

        state.live_state["hum"] = None
        state.live_state["hum_raw"] = None
        state.live_state["vpd"] = None

        # Sicherheitsaktion
        set_fan(False, "(HUM SENSOR STALE)")

    else:
        if hum_stale:
            print("✅ HUM SENSOR wieder da")
        hum_stale = False

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

def do_energy_day_reset():
    """
    Setzt für ALLE Geräte den Tages-Offset auf den aktuellen Rohwert.
    Ergebnis: today = 0.0 für alle Geräte.
    """
    today_str = datetime.date.today().isoformat()

    config.setdefault("ENERGY_DAY_OFFSET", {})

    with energy_lock:
        snapshot = dict(energy_state)

    if not snapshot:
        print("⚠️ ENERGY: Auto-Tagesreset übersprungen (keine Daten)")
        return False

    for dev, e in snapshot.items():
        raw = float(e.get("raw_total", 0.0))

        config["ENERGY_DAY_OFFSET"][dev] = {
            "day": today_str,
            "offset": raw
        }

    config["ENERGY_LAST_DAY_RESET"] = today_str
    save_config(config)

    print("📅 ENERGY: Auto-Tagesreset durchgeführt")
    return True

# =========================================
# 📝 INFOLOG (Watchdog / Systemlog)
# =========================================


infolog_lock = threading.Lock()

def log_event(msg, level="INFO"):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {level}: {msg}\n"

    try:
        with open(LOG_FILE, "a") as f:
            f.write(line)
    except Exception as e:
        print("❌ Log write error:", e)





# =========================================
# 🔌 SHELLY-FUNKTIONEN
# =========================================

def shelly_set(ip, relay, state):
    try:
        url = f"http://{ip}/relay/{relay}?turn={'on' if state else 'off'}"
        requests.get(url, timeout=3)
        return True
    except Exception as e:
        print(f"❌ Shelly SET Fehler {ip} R{relay}:", e)
        return False

def get_shelly_energy(ip, relay, device_key, timeout=3):
    """
    Liefert:
      power (W)
      raw_total (kWh)
      total (kWh seit TOTAL-Reset)
      today (kWh seit Tagesstart/Auto-Reset)
    """

    try:
        url = f"http://{ip}/rpc/Switch.GetStatus?id={int(relay)}"
        r = requests.get(url, timeout=timeout)

        if r.status_code != 200:
            return None

        data = r.json()
        if not isinstance(data, dict):
            return None

        power = data.get("apower")                       # W
        total_wh = data.get("aenergy", {}).get("total")  # Wh

        if power is None or total_wh is None:
            return None

        raw_total_kwh = float(total_wh) / 1000.0

        # =========================================
        # 🔁 TOTAL RESET (Gesamt seit Reset)
        # =========================================
        resets = config.setdefault("ENERGY_RESET", {})

        # Wenn für device noch kein Offset existiert → 0.0
        offset_total = resets.get(device_key, 0.0)
        if offset_total is None:
            offset_total = raw_total_kwh
            resets[device_key] = raw_total_kwh
            save_config(config)

        offset_total = float(offset_total)
        total_kwh = max(0.0, raw_total_kwh - offset_total)

        # =========================================
        # 📅 TODAY (Tagesverbrauch)
        # =========================================
        today_str = datetime.date.today().isoformat()
        day_offsets = config.setdefault("ENERGY_DAY_OFFSET", {})

        # Wenn nicht existiert oder falscher Tag → neu setzen
        if (
            device_key not in day_offsets
            or not isinstance(day_offsets[device_key], dict)
            or day_offsets[device_key].get("day") != today_str
        ):
            day_offsets[device_key] = {
                "day": today_str,
                "offset": raw_total_kwh
            }
            save_config(config)

        offset_today = day_offsets[device_key].get("offset", raw_total_kwh)
        if offset_today is None:
            offset_today = raw_total_kwh
            day_offsets[device_key]["offset"] = raw_total_kwh
            save_config(config)

        offset_today = float(offset_today)
        today_kwh = max(0.0, raw_total_kwh - offset_today)

        return {
            "power": round(float(power), 1),
            "raw_total": round(raw_total_kwh, 3),
            "total": round(total_kwh, 3),
            "today": round(today_kwh, 3),
            "offset_total": round(offset_total, 3),
            "offset_today": round(offset_today, 3),
        }

    except Exception as e:
        print("❌ Shelly Energy Fehler:", e)
        return None

def refresh_energy_state():
    global energy_state

    ENERGY_DEVICES = {
        "heating": ("IP_HEATING", "RELAY_HEATING"),
        "light":   ("IP_LIGHT",   "RELAY_LIGHT"),
        "fan":     ("IP_FAN",     "RELAY_FAN"),
        "vent":    ("IP_VENT",    "RELAY_VENT"),

        # falls vorhanden:
        "irrigation":   ("IP_IRRIGATION",   "RELAY_IRRIGATION"),
        "humidifier":   ("IP_HUMIDIFIER",   "RELAY_HUMIDIFIER"),
        "dehumidifier": ("IP_DEHUMIDIFIER", "RELAY_DEHUMIDIFIER"),
        "light2":       ("IP_LIGHT2",       "RELAY_LIGHT2"),
        "vent2":        ("IP_VENT2",        "RELAY_VENT2"),
    }

    with energy_lock:
        energy_state.clear()
    
        for name, (ip_k, r_k) in ENERGY_DEVICES.items():
            ip = config.get(ip_k)
            relay = config.get(r_k)
    
            if not ip or relay is None:
                continue
    
            e = get_shelly_energy(ip, relay, name)
            if e:
                energy_state[name] = e

def get_shelly_relay_state(ip, relay, timeout=3):
    relay = int(relay)

    # ---------- Gen2 / Strip / Pro ----------
    try:
        url = f"http://{ip}/rpc/Switch.GetStatus?id={relay}"
        r = requests.get(url, timeout=timeout)

        if r.status_code != 200:
            return None

        data = r.json()

        # ❌ Strip antwortet gern mit leerem oder kaputtem JSON
        if not isinstance(data, dict):
            return None

        if "output" not in data:
            return None

        if not isinstance(data["output"], bool):
            return None

        return data["output"]

    except Exception:
        pass

    # ---------- Gen1 Fallback ----------
    try:
        url = f"http://{ip}/status"
        r = requests.get(url, timeout=timeout)

        if r.status_code != 200:
            return None

        data = r.json()

        if "relays" not in data:
            return None

        if relay >= len(data["relays"]):
            return None

        return bool(data["relays"][relay].get("ison", False))

    except Exception:
        return None

def get_today_kwh(device_key, raw_total_kwh):
    today_str = datetime.date.today().isoformat()

    offsets = config.setdefault("ENERGY_DAY_OFFSET", {})

    if (
        device_key not in offsets
        or offsets[device_key].get("day") != today_str
    ):
        offsets[device_key] = {
            "day": today_str,
            "offset": float(raw_total_kwh)
        }
        save_config(config)

    offset = float(offsets[device_key].get("offset", raw_total_kwh))
    return max(0.0, float(raw_total_kwh) - offset)


def switch_shelly(ip, relay, state, timeout=3):
    relay = int(relay)

    # =========================
    # Gen2 / Pro API
    # =========================
    try:
        url = f"http://{ip}/rpc/Switch.Set"
        payload = {
            "id": relay,
            "on": bool(state)
        }

        r = requests.post(url, json=payload, timeout=timeout)

        if r.status_code == 200:
            return True

    except Exception:
        pass

    # =========================
    # Gen1 Fallback
    # =========================
    try:
        url = f"http://{ip}/relay/{relay}?turn={'on' if state else 'off'}"
        r = requests.get(url, timeout=timeout)

        if r.status_code == 200:
            return True

    except Exception as e:
        print(f"❌ Shelly Fehler {ip} Relay {relay}:", e)

    return False

    

# =========================================
# 🌡️ PROFIL & RAMPE
# =========================================




def get_profile():

    now_min = minutes_now()

    day_start = int(config["DAY_START_MIN"])
    night_start = int(config["NIGHT_START_MIN"])

    if is_night(now_min, night_start, day_start):
        profile = "NACHT"
    else:
        profile = "TAG"

    if profile != state.current_profile:
        state.current_profile = profile

    state.live_state["profile"] = profile

    return profile

def check_ramp_schedule():

    now_min = minutes_now()

    day_start = int(config["DAY_START_MIN"])
    night_start = int(config["NIGHT_START_MIN"])

    duration = int(config["RAMP_DURATION_MIN"])

    evening_start = (night_start - duration) % 1440
    morning_start = (day_start - duration) % 1440

def get_active_profile():
    return PROFILES.get("active")




# =========================================
# 🔥 AKTOREN
# =========================================
def set_heating(state, reason=""):
    global heating_on

    if state == heating_on:
        return

    if not switch_shelly(
        config.get("IP_HEATING"),
        config.get("RELAY_HEATING"),
        state
    ):
        return

    heating_on = state
    state.live_state["heating"] = state
    print(("🔥 HEIZUNG EIN " if state else "❄️ HEIZUNG AUS ") + reason)

def set_fan(state, reason=""):
    global fan_on

    if state == fan_on:
        return
    
    if not switch_shelly(
        config.get("IP_FAN"),
        config.get("RELAY_FAN"),
        state
    ):
        return

    fan_on = state
    state.live_state["fan"] = state
    print(("💨 UMLUFT EIN " if state else "🛑 UMLUFT AUS ") + reason)

def set_light(state, reason=""):
    global light_on

    if state == light_on:
        return
    
    if not switch_shelly(
        config.get("IP_LIGHT"),
        config.get("RELAY_LIGHT"),
        state
    ):
        return

    light_on = state
    state.live_state["light"] = state
    print(("💡 LICHT EIN " if state else "🛑 LICHT AUS ") + reason)

def set_vent(state, reason=""):
    global vent_on

    if state == vent_on:
        return
    
    if not switch_shelly(
        config.get("IP_VENT"),
        config.get("RELAY_VENT"),
        state
    ):
        return

    vent_on = state
    state.live_state["vent"] = state
    print(("🌀 VENTILATOR EIN " if state else "🛑 VENTILATOR AUS ") + reason)

def set_irrigation(state, reason=""):
    global irrigation_on

    if state == irrigation_on:
        return
    
    if not switch_shelly(
        config.get("IP_IRRIGATION"),
        config.get("RELAY_IRRIGATION"),
        state
    ):
        return
    irrigation_on = state
    state.live_state["irrigation"] = state
    print(("🚿 BEWÄSSERUNG EIN " if state else "🛑 BEWÄSSERUNG AUS ") + reason)

def set_humidifier(state, reason=""):
    global humidifier_on

    if state == humidifier_on:
        return
    
    if not switch_shelly(
        config.get("IP_HUMIDIFIER"),
        config.get("RELAY_HUMIDIFIER"),
        state
    ):
        return
    humidifier_on = state
    state.live_state["humidifier"] = state
    print(("💧 LUFTBEFEUCHTER EIN " if state else "🛑 LUFTBEFEUCHTER AUS ") + reason)

def set_dehumidifier(state, reason=""):
    global dehumidifier_on

    if state == dehumidifier_on:
        return
    
    if not switch_shelly(
        config.get("IP_DEHUMIDIFIER"),
        config.get("RELAY_DEHUMIDIFIER"),
        state
    ):
        return
    dehumidifier_on = state
    state.live_state["dehumidifier"] = state
    print(("💨 LUFTENTFEUCHTER EIN " if state else "🛑 LUFTENTFEUCHTER AUS ") + reason)

def set_light2(state, reason=""):
    global light2_on

    if state == light2_on:
        return
    
    if not switch_shelly(
        config.get("IP_LIGHT2"),
        config.get("RELAY_LIGHT2"),
        state
    ):
        return
    light2_on = state
    state.live_state["light2"] = state
    print(("💡 LIGHT2 EIN " if state else "🛑 LIGHT2 AUS ") + reason)

def set_vent2(state, reason=""):
    global vent2_on

    if state == vent2_on:
        return
    
    if not switch_shelly(
        config.get("IP_VENT2"),
        config.get("RELAY_VENT2"),
        state
    ):
        return
    vent2_on = state
    state.live_state["vent2"] = state
    print(("🌀 VENT2 EIN " if state else "🛑 VENT2 AUS ") + reason)

# =========================================
# 🔌 DEVICE SETTER MAPPING
# =========================================

DEVICE_SETTERS = {
    "fan": set_fan,
    "vent": set_vent,
    "heating": set_heating,
    "light": set_light,
    "light2": set_light2,
    "vent2": set_vent2
}

# =========================================
# 🔌 GENERIC DEVICE CONTROL SYSTEM
# =========================================

def get_device_mode(device):
    modes = config.setdefault("DEVICE_MODES", {})
    return modes.get(device, "OFF")


def get_device_params(device):
    params = config.setdefault("DEVICE_PARAMS", {})
    return params.setdefault(device, {})


def set_device(device, state):
    setter = DEVICE_SETTERS.get(device)
    if setter:
        setter(state)

def control_time_mode(device):
    params = get_device_params(device)
    now_min = minutes_now()

    start = int(params.get("start_min", 0))
    end   = int(params.get("end_min", 0))

    set_device(device, in_time_window(now_min, start, end))


def in_time_window(now_min, start, end):
    if start < end:
        return start <= now_min < end
    else:
        return now_min >= start or now_min < end






def failsafe_check(device, ip_key, relay_key):

    ip = config.get(ip_key)
    relay = config.get(relay_key)

    if not ip or relay is None:
        return

    should_on = state.live_state.get(device)
    actual = get_shelly_relay_state(ip, relay)

    if actual is None:
        print(f"🚨 FAILSAFE {device}: Shelly nicht erreichbar")
        return

    if actual != should_on:
        print(f"🛡️ FAILSAFE {device}: korrigiere Zustand")
        switch_shelly(ip, relay, should_on)



# =========================================
# 🌡️ REGELLOGIK
# =========================================


def update_humidity_setpoint():
    profile = get_profile()

    if profile == "TAG":
        base, tol = config["DAY_HUM"], config["DAY_HUM_TOL"]
    else:
        base, tol = config["NIGHT_HUM"], config["NIGHT_HUM_TOL"]

    state.live_state["hum_target"] = base
    state.live_state["hum_tol"] = tol

def update_temperature_setpoint():
    profile = get_profile()

    if profile == "TAG":
        base = float(config["DAY_TEMP"])
        tol  = float(config["DAY_TEMP_TOL"])
    else:
        base = float(config["NIGHT_TEMP"])
        tol  = float(config["NIGHT_TEMP_TOL"])

    target = base

    if state.ramp_active:

        ramp_target = get_ramped_target()

        if ramp_target is not None:
            target = ramp_target

    update_ramp()

    # 📊 IMMER setzen – auch wenn Regelung deaktiviert
    state.live_state["temp_target"] = target
    state.live_state["temp_tol"] = tol

def evaluate_env_conditions(device):

    cfg = config.get("DEVICE_ENV_CONFIG", {}).get(device, {})
    if not cfg:
        return False

    use_temp = cfg.get("use_temp", False)
    use_hum = cfg.get("use_hum", False)
    logic = cfg.get("logic", "OR")
    direction = cfg.get("direction", "HIGH")  # HIGH oder LOW

    results = []

    # ================= TEMP =================
    if use_temp:
        temp = state.live_state.get("temp")
        target = state.live_state.get("temp_target")
        tol = state.live_state.get("temp_tol")

        if None not in (temp, target, tol):

            if direction == "HIGH":
                results.append(temp > (target + tol))
            else:  # LOW
                results.append(temp < (target - tol))

    # ================= HUM =================
    if use_hum:
        hum = state.live_state.get("hum")
        target = state.live_state.get("hum_target")
        tol = state.live_state.get("hum_tol")

        if None not in (hum, target, tol):

            if direction == "HIGH":
                results.append(hum > (target + tol))
            else:
                results.append(hum < (target - tol))

    if not results:
        return False

    if logic == "AND":
        return all(results)

    return any(results)


def control_device(device):

    mode = get_device_mode(device)
    params = get_device_params(device)

    now_min = minutes_now()

    # OFF
    if mode == "OFF":
        set_device(device, False)
        return

    # Dauerbetrieb
    if mode == "ON":
        set_device(device, True)
        return

    # Zeitgesteuert
    if mode == "TIME":
        start = int(params.get("start_min", 0))
        end   = int(params.get("end_min", 0))
        should_run = in_time_window(now_min, start, end)
        set_device(device, should_run)
        return

    # Intervall
    if mode == "INTERVAL":
        on_t  = int(params.get("interval_on", 300))
        off_t = int(params.get("interval_off", 900))

        cycle = on_t + off_t
        phase = int(time.time()) % cycle

        set_device(device, phase < on_t)
        return

    # Umgebung
    if mode == "ENV":
        if device == "heating":
            control_heating_env()
            return
        
        if device == "light":
            control_light_profile()
            return
        
        should_run = evaluate_env_conditions(device)
        set_device(device, should_run)
        return
    
def control_light_profile():
    now_min = minutes_now()

    day_start = int(config.get("DAY_START_MIN", 360))
    night_start = int(config.get("NIGHT_START_MIN", 1320))

    # Licht an = Tageszeit
    light_on = in_time_window(now_min, day_start, night_start)

    set_device("light", light_on)


def control_heating_env():
    """
    Temperaturregelung im ENV Modus.
    Nutzt Profil + Rampen + Hysterese.
    """

    temp = state.live_state.get("temp")
    if temp is None:
        set_heating(False)
        return

    update_temperature_setpoint()

    target = state.live_state.get("temp_target")
    tol    = state.live_state.get("temp_tol")

    if target is None or tol is None:
        return

    min_temp = float(config.get("MIN_TEMP", 18.0))
    max_temp = float(config.get("MAX_TEMP", 30.0))

    # 🔴 Absolute Sicherheitsgrenzen
    if temp >= max_temp:
        set_heating(False, "(MAX TEMP Schutz)")
        return

    if temp <= min_temp:
        set_heating(True, "(MIN TEMP Schutz)")
        return

    # 🟢 Normale Hysterese-Regelung
    # Einschalten unter Soll - Toleranz
    if temp < (target - tol):
        set_heating(True, f"(unter Soll {target:.1f}°C)")

    # Ausschalten erst wenn Soll erreicht
    elif temp >= target:
        set_heating(False, f"(Soll {target:.1f}°C erreicht)")

    #print("HEATING ENV CHECK:",
      #"Temp:", temp,
      #"Target:", target,
      #"Tol:", tol,
      #"Mode:", get_device_mode("heating"))


def control_fan_env():
    should_run = evaluate_env_conditions("fan")
    set_fan(should_run)



def control_ventilator_env():
    """
    Umgebungskühlung:
    Ventilator läuft, wenn Temperatur über Soll + Toleranz.
    Sollwerte kommen aus aktivem Profil.
    """

    temp = state.live_state.get("temp")
    if temp is None:
        set_vent(False)
        return

    # Aktuelle Zielwerte holen
    profile = get_profile()

    if profile == "TAG":
        target = float(config.get("DAY_TEMP", 24.0))
        tol    = float(config.get("DAY_TEMP_TOL", 1.0))
    else:
        target = float(config.get("NIGHT_TEMP", 20.0))
        tol    = float(config.get("NIGHT_TEMP_TOL", 1.0))

    # Sicherheitsgrenze
    if temp > config.get("MAX_TEMP", 30.0):
        set_vent(True, "(MAX TEMP Schutz)")
        return

    # Regelung
    if temp > (target + tol):
        set_vent(True, f"(Kühlung über Soll {target:.1f}°C)")
    elif temp <= target:
        set_vent(False, f"(Soll {target:.1f}°C erreicht)")


# =========================================

PROFILE_FILE = "profiles.json"

def load_profiles():
    if os.path.exists(PROFILE_FILE):
        with open(PROFILE_FILE, "r") as f:
            return json.load(f)
    raise RuntimeError("profiles.json fehlt")

def save_profiles(p):
    with open(PROFILE_FILE, "w") as f:
        json.dump(p, f, indent=2)

PROFILES = load_profiles()

def apply_profile(name):


    if name not in PROFILES["profiles"]:
        return False

    PROFILES["active"] = name
    profile = PROFILES["profiles"][name]

    # 🔁 Profilwerte ins config übernehmen
    for k, v in profile.items():
        config[k] = v

    # 💾 speichern
    save_profiles(PROFILES)
    save_config(config)

    # =========================
    # 🔄 SCHRITT 4: Rampe zurücksetzen
    # =========================
    state.ramp_active = False
    stop_ramp()

    state.live_state["ramp_active"] = False
    state.live_state["ramp_target"] = None

    print(f"🔁 Profilwechsel → Rampe zurückgesetzt ({name})")

    return True

# =========================================

def sync_relay(name, ip, relay, state_var, live_key):
    # nicht konfiguriert
    if not ip or relay is None:
        globals()[state_var] = None
        state.live_state[live_key] = None
        return

    relay_state = get_shelly_relay_state(ip, relay)

    # ❌ FEHLER / KEINE VERBINDUNG
    if relay_state is None:
        globals()[state_var] = None
        state.live_state[live_key] = None

        print(f"❌ {name}: KEINE VERBINDUNG (IP {ip}, Relay {relay})")
        return

    # ✅ OK
    globals()[state_var] = relay_state
    state.live_state[live_key] = relay_state

    print(f"✅ {name}: {'EIN' if relay_state else 'AUS'} (IP {ip}, Relay {relay})")


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
    global last_ds_time, last_dht_time
    global last_ds_temp, last_hum
    global MQTT_LAST_MSG
    
    MQTT_LAST_MSG = time.time()


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

        with state_lock:
            last_ds_temp = temp_raw
            last_ds_time = now

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

        with state_lock:
            last_hum = hum_raw
            last_dht_time = now

            state.live_state["hum_raw"] = hum_raw
            state.live_state["hum"] = hum

        # Optional debug
        # print(f"💧 HUM {hum:.2f}%")

        return
    
# =========================================
# 🧵 SHELLY + ENERGY THREAD (NON-BLOCKING MAINLOOP)
# =========================================

def shelly_background_loop():
    global last_energy_poll, last_failsafe_poll

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
            if now - last_failsafe_poll >= FAILSAFE_INTERVAL:
                last_failsafe_poll = now

                with shelly_lock:
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
            if now - last_energy_poll >= ENERGY_INTERVAL:
                last_energy_poll = now

                tmp = {}

                # config sicher lesen
                with shelly_lock:
                    for name, (ip_k, r_k) in ENERGY_DEVICES.items():
                        ip = config.get(ip_k)
                        relay = config.get(r_k)

                        if not ip or relay is None:
                            continue

                        e = get_shelly_energy(ip, relay, name, timeout=2)
                        if e:
                            tmp[name] = e

                # atomar übernehmen
                with energy_lock:
                    energy_state.clear()
                    energy_state.update(tmp)

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

                with shelly_lock:
                    do_energy_day_reset()

                # WICHTIG: Sofort merken, dass wir heute resettet haben
                config["ENERGY_LAST_DAY_RESET"] = today_key
                save_config(config)




        except Exception as e:
            print("❌ Shelly Background Thread Fehler:", e)

        time.sleep(1)
    
# =========================================
# 📡 MQTT SENSOR THREAD
# =========================================

def mqtt_sensor_thread():
    """
    Läuft dauerhaft im Hintergrund.
    MQTT darf disconnecten → reconnectet automatisch.
    Mainloop läuft IMMER weiter.
    """

    while True:
        try:
            print("📡 MQTT Thread startet...")

            client = mqtt.Client(
                client_id="grow-backend",
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2
            )

            client.on_connect = on_connect
            client.on_message = on_message

            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=30)

            # wichtig: loop_forever blockiert NUR diesen Thread
            client.loop_forever(retry_first_connection=True)

        except Exception as e:
            print("❌ MQTT Thread Fehler:", e)

        print("🔁 MQTT Thread reconnect in 5s...")
        time.sleep(5)


# =========================================
# 🐶 WATCHDOG THREAD
# =========================================

WATCHDOG_INTERVAL = 5  # Sekunden

def watchdog_loop():
    last_warn_temp = 0
    last_warn_hum = 0
    last_warn_energy = 0

    while True:
        try:
            now = time.time()

            # -------------------------
            # 🌡️ TEMP stale?
            # -------------------------
            with state_lock:
                ds_age = now - last_ds_time
                dht_age = now - last_dht_time

            if ds_age > SENSOR_TIMEOUT:
                # nicht spammen -> max alle 60s
                if now - last_warn_temp > 60:
                    log_event(f"TEMP Sensor stale: {int(ds_age)}s keine Daten", "WARN")
                    last_warn_temp = now

            if dht_age > SENSOR_TIMEOUT:
                if now - last_warn_hum > 60:
                    log_event(f"HUM Sensor stale: {int(dht_age)}s keine Daten", "WARN")
                    last_warn_hum = now

            # -------------------------
            # ⚡ Energy stale?
            # -------------------------
            with energy_lock:
                snapshot = dict(energy_state)

            # Wenn wir z.B. keine Daten haben
            if not snapshot:
                if now - last_warn_energy > 60:
                    log_event("ENERGY: keine Daten (energy_state leer)", "WARN")
                    last_warn_energy = now

            # Optional: check ob Werte alt sind
            # (wenn du später timestamp in energy_state speicherst)

        except Exception as e:
            log_event(f"Watchdog Fehler: {e}", "ERROR")

        time.sleep(WATCHDOG_INTERVAL)



# =========================================
# 🌐 FLASK WEB-UI
# =========================================
flask_app = Flask(__name__)

@flask_app.route("/")
def dashboard():
    return render_template("dashboard.html")

@flask_app.route("/settings")
def settings():
    return render_template("settings.html", config=config)

@flask_app.route("/sensoren")
def sensoren_page():
    return render_template("sensoren.html")

@flask_app.route("/diagrams")
def diagrams_page():
    return render_template("diagrams.html")

@flask_app.route("/temperature")
def temperature_page():
    return render_template("temperature.html")

@flask_app.route("/humidity")
def humidity_page():
    return render_template("humidity.html")

@flask_app.route("/vpd")
def vpd_page():
    return render_template("vpd.html")

@flask_app.route("/ventilator")
def ventilator_page():
    return render_template("ventilator.html")

@flask_app.route("/heizung")
def heizung_page():
    return render_template("heizung.html")

@flask_app.route("/licht")
def licht_page():
    return render_template("licht.html")

@flask_app.route("/abluft")
def abluft_page():
    return render_template("abluft.html")

@flask_app.route("/system")
def system_page():
    return render_template("system.html")

@flask_app.route("/design")
def design_page():
    return render_template("design.html")

@flask_app.route("/energie")
def energie_page():
    return render_template("energie.html")

@flask_app.route("/pflanzendaten")
def pflanzendaten_page():
    return render_template("pflanzendaten.html")

@flask_app.route("/energie/settings")
def energie_settings_page():
    return render_template("energie_settings.html")

@flask_app.route("/connections")
def connections_page():
    return render_template("connections.html")

@flask_app.route("/tagebuch")
def tagebuch_page():
    return render_template("tagebuch.html")


@flask_app.route("/api/diagrams/export")
def export_diagrams():
    return send_file(
        "data.db",
        as_attachment=True,
        download_name="grow_diagrams.db"
    )

@flask_app.route("/api/diagrams/import", methods=["POST"])
def import_diagrams():
    with open("data.db","wb") as f:
        f.write(request.data)
    return {"status":"ok"}

# =========================================
# Pflanzenprofile Endpunkte
# =========================================
# =========================================
# 🌿 PLANT DATA (6 Pflanzen)
# =========================================


@flask_app.route("/api/plants")
def api_plants():
    """
    Liefert nur ID + Name für Tagebuch Filter
    """
    db = sqlite3.connect("data.db")
    c = db.cursor()
    c.execute("SELECT id, name FROM plants ORDER BY id ASC")
    rows = c.fetchall()
    db.close()

    plants = {}
    for r in rows:
        pid = str(r[0])
        nm = (r[1] or "").strip()
        plants[pid] = nm if nm else f"Pflanze {pid}"

    # Fallback
    for i in range(1, 7):
        plants.setdefault(str(i), f"Pflanze {i}")

    return jsonify(plants)


@flask_app.route("/api/plants/data")
def api_plants_data():
    """
    Liefert alle Daten für alle 6 Pflanzen
    """
    db = sqlite3.connect("data.db")
    c = db.cursor()
    c.execute("""
        SELECT id, name, sativa, indica, seed_date, flower_days, flower_start
        FROM plants
        ORDER BY id ASC
    """)
    rows = c.fetchall()
    db.close()

    out = []
    for r in rows:
        out.append({
            "id": r[0],
            "name": r[1] or f"Pflanze {r[0]}",
            "sativa": r[2],
            "indica": r[3],
            "seed_date": r[4],
            "flower_days": r[5],
            "flower_start": r[6]
        })

    return jsonify(out)


@flask_app.route("/api/plants/data", methods=["POST"])
def api_plants_data_save():
    """
    Speichert alle 6 Pflanzen in einem Rutsch
    """
    data = request.json or {}
    plants = data.get("plants", [])

    if not isinstance(plants, list):
        return {"status": "error", "message": "plants must be a list"}, 400

    db = sqlite3.connect("data.db")
    c = db.cursor()

    for p in plants:
        try:
            pid = int(p.get("id"))
        except:
            continue

        if pid < 1 or pid > 6:
            continue

        name = str(p.get("name") or "").strip()
        if name == "":
            name = f"Pflanze {pid}"

        def to_int(x):
            if x is None or x == "":
                return None
            return int(float(x))

        def to_date(x):
            x = (x or "").strip()
            return x if x else None

        sativa = to_int(p.get("sativa"))
        indica = to_int(p.get("indica"))
        seed_date = to_date(p.get("seed_date"))
        flower_days = to_int(p.get("flower_days"))
        flower_start = to_date(p.get("flower_start"))

        c.execute("""
            UPDATE plants
            SET name=?, sativa=?, indica=?, seed_date=?, flower_days=?, flower_start=?
            WHERE id=?
        """, (name, sativa, indica, seed_date, flower_days, flower_start, pid))

    db.commit()
    db.close()

    return {"status": "ok"}




# =========================================
# ⚡ ENERGY RESET ENDPOINTS (TOTAL + TODAY)
# =========================================

@flask_app.route("/api/energy")
def api_energy():
    with energy_lock:
        return jsonify(energy_state)

@flask_app.route("/api/energy/reset_total/<device>", methods=["POST"])
def api_energy_reset_total_device(device):
    config.setdefault("ENERGY_RESET", {})

    # Reset = Offset auf aktuellen Rohwert setzen
    # (machen wir sofort im Polling, aber hier markieren wir es)
    config["ENERGY_RESET"][device] = None

    save_config(config)
    refresh_energy_state()
    return {"status": "ok", "device": device, "mode": "total"}

@flask_app.route("/api/energy/reset_today/<device>", methods=["POST"])
def api_energy_reset_today_device(device):
    config.setdefault("ENERGY_DAY_OFFSET", {})

    # Tagesoffset wird direkt neu gesetzt (im Polling)
    config["ENERGY_DAY_OFFSET"][device] = None

    save_config(config)
    refresh_energy_state()
    return {"status": "ok", "device": device, "mode": "today"}


@flask_app.route("/api/energy/reset_total_all", methods=["POST"])
def api_energy_reset_total_all():
    config.setdefault("ENERGY_RESET", {})

    # aktuelles energy_state Snapshot holen
    with energy_lock:
        snapshot = dict(energy_state)

    # offsets setzen
    for dev, e in snapshot.items():
        raw = float(e.get("raw_total", 0.0))
        config["ENERGY_RESET"][dev] = raw

    # optional: _all kannst du löschen oder ignorieren
    if "_all" in config["ENERGY_RESET"]:
        del config["ENERGY_RESET"]["_all"]

    save_config(config)
    refresh_energy_state()
    print("🧹 ENERGY: Manueller Total-Reset ALL")

    return {"status": "ok"}


@flask_app.route("/api/energy/reset_today_all", methods=["POST"])
def api_energy_reset_today_all():
    today_str = datetime.date.today().isoformat()

    config.setdefault("ENERGY_DAY_OFFSET", {})

    # aktuelles energy_state Snapshot holen
    with energy_lock:
        snapshot = dict(energy_state)

    # offsets setzen
    for dev, e in snapshot.items():
        raw = float(e.get("raw_total", 0.0))

        config["ENERGY_DAY_OFFSET"][dev] = {
            "day": today_str,
            "offset": raw
        }

    # optional: auch "last reset" setzen, damit Auto Reset heute nicht nochmal feuert
    config["ENERGY_LAST_DAY_RESET"] = today_str

    save_config(config)
    refresh_energy_state()
    print("🧹 ENERGY: Manueller Today-Reset ALL")

    return {"status": "ok"}



# =========================================
# 📔 DIARY ENDPOINTS
# =========================================

@flask_app.route("/api/diary", methods=["GET", "POST"])
def api_diary():

    if request.method == "GET":
        db = sqlite3.connect("data.db")
        c = db.cursor()

        c.execute("""
            SELECT id, ts, plant, action, ph, ec, amount, note
            FROM diary_entries
            ORDER BY ts DESC
            LIMIT 500
        """)

        rows = c.fetchall()
        db.close()

        entries = []
        for r in rows:
            entries.append({
                "id": r[0],
                "ts": r[1],
                "plant": r[2],
                "action": r[3],
                "ph": r[4],
                "ec": r[5],
                "amount": r[6],
                "note": r[7]
            })

        return jsonify(entries)

    # POST
    data = request.json or {}

    ts = int(time.time())
    plant = data.get("plant")
    action = str(data.get("action", "")).strip()
    note = str(data.get("note", "")).strip()

    ph = data.get("ph")
    ec = data.get("ec")
    amount = data.get("amount")

    # sanitize
    try: plant = int(plant) if plant is not None else None
    except: plant = None

    try: ph = float(ph) if ph not in [None, ""] else None
    except: ph = None

    try: ec = float(ec) if ec not in [None, ""] else None
    except: ec = None

    try: amount = float(amount) if amount not in [None, ""] else None
    except: amount = None

    db = sqlite3.connect("data.db")
    c = db.cursor()

    c.execute("""
        INSERT INTO diary_entries (ts, plant, action, ph, ec, amount, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ts, plant, action, ph, ec, amount, note))

    db.commit()
    db.close()

    return jsonify({"status": "ok"})

@flask_app.route("/api/diary/<int:entry_id>", methods=["DELETE"])
def api_diary_delete(entry_id):

    db = sqlite3.connect("data.db")
    c = db.cursor()

    c.execute("DELETE FROM diary_entries WHERE id = ?", (entry_id,))
    db.commit()
    db.close()

    return jsonify({"status": "ok"})

@flask_app.route("/api/state")
def api_state():
    return jsonify({

        # ================= SENSOR =================
        "temp_raw": state.live_state.get("temp_raw"),
        "temp": state.live_state.get("temp"),
        "hum_raw": state.live_state.get("hum_raw"),
        "hum": state.live_state.get("hum"),

        "temp_target": state.live_state.get("temp_target"),
        "temp_tol": state.live_state.get("temp_tol"),
        "hum_target": state.live_state.get("hum_target"),
        "hum_tol": state.live_state.get("hum_tol"),

        "vpd": state.live_state.get("vpd"),

        # ================= PROFILE =================
        "profile": state.current_profile,
        "ramp_active": bool(state.ramp_active and config.get("RAMP_ENABLED", 0)),

        # ================= DEVICES =================
        "heating_on": heating_on,
        "fan_on": fan_on,
        "light_on": light_on,
        "vent_on": vent_on,

        # Modi
        "heating_mode": get_device_mode("heating"),
        "fan_mode": get_device_mode("fan"),
        "light_mode": get_device_mode("light"),
        "vent_mode": get_device_mode("vent"),

        # ================= ENERGY =================
        "energy": energy_state,

        # ================= SENSOR HEALTH =================
        "temp_ok": not temp_stale,
        "hum_ok": not hum_stale,
        "temp_age": int(time.time() - last_ds_time),
        "hum_age": int(time.time() - last_dht_time),

        # optional Debug
        "device_modes": config.get("DEVICE_MODES", {})

    })


@flask_app.route("/api/history")
def api_history():
    range_map = {
        "1h": 1 * 3600,
        "6h": 6 * 3600,
        "24h": 24 * 3600,
        "7d": 7 * 24 * 3600,
    }

    range_key = request.args.get("range", "24h")
    data_type = request.args.get("type", "temp")

    seconds = range_map.get(range_key, 24 * 3600)
    since = int(time.time()) - seconds

    db = sqlite3.connect("data.db")
    c = db.cursor()

    # -----------------------------
    # TEMP
    # -----------------------------
    if data_type == "temp":
        c.execute("""
            SELECT ts, temp, temp_target
            FROM temp_history
            WHERE ts >= ?
            ORDER BY ts ASC
        """, (since,))

        rows = c.fetchall()
        data = [
            {"ts": r[0], "temp": r[1], "target": r[2]}
            for r in rows
            if r[1] is not None
        ]

    # -----------------------------
    # HUMIDITY
    # -----------------------------
    elif data_type == "hum":
        c.execute("""
            SELECT ts, hum, hum_target
            FROM temp_history
            WHERE ts >= ?
            ORDER BY ts ASC
        """, (since,))

        rows = c.fetchall()
        data = [
            {"ts": r[0], "hum": r[1], "target": r[2]}
            for r in rows
            if r[1] is not None
        ]

    # -----------------------------
    # VPD
    # -----------------------------
    elif data_type == "vpd":
        c.execute("""
            SELECT ts, vpd
            FROM temp_history
            WHERE ts >= ?
            ORDER BY ts ASC
        """, (since,))

        rows = c.fetchall()
        data = [
            {"ts": r[0], "vpd": r[1]}
            for r in rows
            if r[1] is not None
        ]

    else:
        data = []

    db.close()
    return jsonify(data)

# =========================================
# 🔌 DEVICE MODE API
# =========================================

@flask_app.route("/api/device/<device>", methods=["GET", "POST"])
def api_device(device):

    config.setdefault("DEVICE_MODES", {})
    config.setdefault("DEVICE_PARAMS", {})

    if request.method == "GET":
        return jsonify({
            "mode": config["DEVICE_MODES"].get(device, "OFF"),
            "params": config["DEVICE_PARAMS"].get(device, {})
        })

    # POST
    data = request.json or {}

    mode = data.get("mode")
    params = data.get("params", {})

    if mode:
        config["DEVICE_MODES"][device] = mode

    config["DEVICE_PARAMS"].setdefault(device, {}).update(params)

    save_config(config)

    return {"status": "ok"}

@flask_app.route("/api/device/mode/<device>", methods=["POST"])
def api_set_device_mode(device):
    data = request.json or {}

    config.setdefault("DEVICE_MODES", {})
    config.setdefault("DEVICE_ENV_CONFIG", {})

    if "DEVICE_MODES" in data:
        config["DEVICE_MODES"][device] = data["DEVICE_MODES"][device]

    if "DEVICE_ENV_CONFIG" in data:
        config["DEVICE_ENV_CONFIG"][device] = data["DEVICE_ENV_CONFIG"][device]

    save_config(config)

    return {"status":"ok"}


@flask_app.route("/api/config", methods=["GET", "POST"])
def api_config():

    if request.method == "GET":
        return jsonify({
            **config,
            "ACTIVE_PROFILE": PROFILES.get("active")
        })

    data = request.json or {}

    # =========================================
    # 🔧 CONFIG UPDATE
    # =========================================
    for key, value in data.items():

        # =========================
        # 🎨 DASHBOARD
        # =========================
        if key.startswith("DASH_"):
            config[key] = value
            continue

        # =========================
        # 🔌 DEVICE MODES (MERGE!)
        # =========================
        if key == "DEVICE_MODES":
            config.setdefault("DEVICE_MODES", {})
            config["DEVICE_MODES"].update(value)
            continue

        if key == "DEVICE_PARAMS":
            config.setdefault("DEVICE_PARAMS", {})
            for dev, params in value.items():
                config["DEVICE_PARAMS"].setdefault(dev, {})
                config["DEVICE_PARAMS"][dev].update(params)
            continue

        if key == "DEVICE_ENV_CONFIG":
            config.setdefault("DEVICE_ENV_CONFIG", {})
            for dev, env in value.items():
                config["DEVICE_ENV_CONFIG"].setdefault(dev, {})
                config["DEVICE_ENV_CONFIG"][dev].update(env)
            continue

        # =========================
        # 🌐 IP STRINGS
        # =========================
        if key.startswith("IP_"):
            config[key] = str(value).strip()
            continue

        # =========================
        # 🔌 RELAYS
        # =========================
        if key.startswith("RELAY_"):
            try:
                config[key] = int(value)
            except:
                pass
            continue

        # =========================
        # 🔢 INT SPECIAL
        # =========================
        if key in ["ENERGY_DAY_RESET_MIN"]:
            try:
                config[key] = int(value)
            except:
                pass
            continue

        # =========================
        # 🔢 FLOAT FALLBACK
        # =========================
        try:
            config[key] = float(value)
        except:
            config[key] = value

    # =========================================
    # 🔁 RAMP RESYNC
    # =========================================
    RAMP_RELEVANT_KEYS = {
        "DAY_TEMP",
        "NIGHT_TEMP",
        "RAMP_DURATION_MIN"
    }

    if state.ramp_active:

        if "RAMP_DURATION_MIN" in data:
            update_ramp_duration()
        
        if (
            "DAY_TEMP" in data
            or "NIGHT_TEMP" in data
                ):
            resync_active_ramp()

    # =========================================
    # 🛑 RAMP STOP IF DISABLED
    # =========================================
    if not config.get("RAMP_ENABLED", 0):
        stop_ramp()

        state.live_state["ramp_active"] = False
        state.live_state["ramp_target"] = None

    # =========================================
    # 💾 SAVE CONFIG
    # =========================================
    save_config(config)

    # =========================================
    # 🔒 MIRROR INTO ACTIVE PROFILE
    # =========================================
    active = PROFILES.get("active")

    DESIGN_KEYS = {
        "DASH_ENV",
        "DASH_ENV_ORDER",
        "DASH_DEVICE_ORDER",
        "DEVICE_MODES",
        "DEVICE_PARAMS",
        "DEVICE_ENV_CONFIG"
    }

    if active and active in PROFILES.get("profiles", {}):
        profile = PROFILES["profiles"][active]

        for k in profile.keys():
            if k in config and k not in DESIGN_KEYS:
                profile[k] = config[k]

        save_profiles(PROFILES)

    return jsonify({
        "status": "ok",
        "config": config
    })

@flask_app.route("/api/reset_history", methods=["POST"])
def api_reset_history():
    try:
        db = sqlite3.connect("data.db")
        c = db.cursor()

        # 🔥 ALLE Diagramm-Daten löschen
        c.execute("DELETE FROM temp_history")

        db.commit()
        db.close()

        print("🧹 Diagramm-Historie zurückgesetzt")

        return jsonify({
            "status": "ok",
            "message": "Diagramm-Historie gelöscht"
        })

    except Exception as e:
        print("❌ Reset Fehler:", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@flask_app.route("/api/profile/<name>", methods=["POST"])
def api_set_profile(name):
    ok = apply_profile(name)
    if not ok:
        return {"error": "unknown profile"}, 404

    return {"status": "ok", "active": name}


@flask_app.route("/api/profile")
def get_profile_api():
    return {"active": PROFILES.get("active")}

# =========================================
# 🐶 WATCHDOG + INFOLOG API
# =========================================

@flask_app.route("/watchdog")
def watchdog_page():
    return render_template("watchdog.html")

@flask_app.route("/api/watchdog/log")
def api_watchdog_log():
    lines = int(request.args.get("lines", 300))
    level = request.args.get("level", "ALL")

    if not os.path.exists(LOG_FILE):
        return jsonify({"lines": []})

    try:
        with open(LOG_FILE, "r") as f:
            all_lines = f.readlines()

        filtered = []

        for line in all_lines:
            if level == "ALL":
                filtered.append(line)
            elif f"{level}:" in line:
                filtered.append(line)

        return jsonify({
            "lines": filtered[-lines:]
        })

    except Exception as e:
        return jsonify({
            "lines": [f"❌ Fehler beim Lesen: {e}"]
        })


@flask_app.route("/api/watchdog/log/clear", methods=["POST"])
def api_watchdog_log_clear():
    try:
        open(LOG_FILE, "w").close()
        log_event("Log wurde manuell geleert")
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@flask_app.route("/api/watchdog/log/download")
def api_watchdog_log_download():
    if not os.path.exists(LOG_FILE):
        return {"error": "Kein Log vorhanden"}, 404

    return send_file(
        LOG_FILE,
        as_attachment=True,
        download_name="infolog.txt"
    )


@flask_app.route("/api/watchdog/status")
def api_watchdog_status():
    now = time.time()

    with state_lock:
        ds_age = now - last_ds_time if last_ds_time else 999999
        dht_age = now - last_dht_time if last_dht_time else 999999

    with energy_lock:
        ecount = len(energy_state)

    mqtt_age = now - MQTT_LAST_MSG if MQTT_LAST_MSG else 999999

    return jsonify({
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        "temp": {
            "age": int(ds_age),
            "stale": ds_age > SENSOR_TIMEOUT
        },
        "hum": {
            "age": int(dht_age),
            "stale": dht_age > SENSOR_TIMEOUT
        },
        "mqtt": {
            "age": int(mqtt_age),
            "stale": mqtt_age > 30  # MQTT sollte öfter kommen
        },
        "energy": {
            "devices": ecount,
            "stale": ecount == 0
        }
    })


def run_flask():
    flask_app.run(host="0.0.0.0", port=5000, debug=False)


threading.Thread(target=run_flask, daemon=True).start()
print("🌐 Flask Webserver gestartet")
threading.Thread(target=shelly_background_loop, daemon=True).start()
print("🧵 Shelly Background Thread gestartet")
threading.Thread(target=mqtt_sensor_thread, daemon=True).start()
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

        # =========================================
        # 🔁 Rampen-Sollwert regelmäßig aktualisieren
        # =========================================
        if state.ramp_active:
            update_ramp_target_only()

        # =========================================
        # 🧊 SENSOR STALE LOGIK (niemals blockieren)
        # =========================================
        mark_stale_sensors()

        # Snapshot (threadsafe)
        with state_lock:
            temp_val = state.live_state.get("temp")
            hum_val = state.live_state.get("hum")

        # =========================================
        # 📊 VPD + DB Logging (entkoppelt von MQTT)
        # =========================================
        if now - last_db_write >= DB_INTERVAL:
            last_db_write = now

            with state_lock:

                # Targets können None sein, ist OK
                tt = state.live_state.get("temp_target")
                ht = state.live_state.get("hum_target")

            if temp_val is not None and hum_val is not None:
                vpd = calculate_vpd(temp_val, hum_val)

                with state_lock:
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


