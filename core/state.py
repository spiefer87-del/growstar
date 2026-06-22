# =========================================
# 📊 LIVE STATUS (für Web-UI)
# =========================================
live_state = {
    "temp": None,
    "temp_raw": None,
    "hum": None,
    "hum_raw": None,
    "vpd": None,

    "profile": None,

    # Sollwerte (für Dashboard)
    "temp_target": None,
    "temp_tol": None,
    "hum_target": None,
    "hum_tol": None,

    "heating": False,
    "fan": False,
    "light": False,

    "ramp_active": False,
    "ramp_target": None,

}

live_state["energy"] = {
    "heating": {
        "power": None,
        "total": None
    },
    "light": {
        "power": None,
        "total": None
    }
}


# =========================================
# 🧠 INTERNE STATUSVARIABLEN
# =========================================

heating_on = False
fan_on = False
light_on = False
vent_on = False
irrigation_on = False
humidifier_on = False
dehumidifier_on = False
light2_on = False
vent2_on = False

# Rohwerte
last_temp_raw = None
last_hum_raw = None

# Korrigierte Werte (für Regelung & UI)
last_ds_temp = None
last_hum = None

last_ds_time = 0
last_dht_time = 0
last_db_write = 0

current_profile = None

# Rampe
ramp_active = False
ramp_start_ts = None
ramp_end_ts = None
ramp_start_temp = None
ramp_target_temp = None

# Sensor Stale-Flags
temp_stale = False
hum_stale = False
