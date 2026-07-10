import os
import json

CONFIG_FILE = "config.json"

# =========================================
# 🔧 DYNAMISCHE KONFIGURATION (Web-UI)
# =========================================
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

config = load_config()

# =========================================
# 🧠 DEFAULT CONFIG (neue Architektur)
# =========================================
DEFAULT_CONFIG = {

    # ================= PROFIL =================
    "DAY_START_MIN": 360,
    "NIGHT_START_MIN": 1320,

    "DAY_TEMP": 24.0,
    "DAY_TEMP_TOL": 1.0,
    "DAY_HUM": 55.0,
    "DAY_HUM_TOL": 5.0,

    "NIGHT_TEMP": 20.0,
    "NIGHT_TEMP_TOL": 1.0,
    "NIGHT_HUM": 60.0,
    "NIGHT_HUM_TOL": 5.0,

    "MIN_TEMP": 12.0,
    "MAX_TEMP": 30.0,
    "MAX_HUM": 75.0,

    "TEMP_OFFSET": 0.0,
    "HUM_OFFSET": 0.0,

    "RAMP_DURATION_MIN": 60,
    "RAMP_ENABLED": 0,

    "SENSOR_ASSIGNMENTS": {

        "temperature": {
            "source": "legacy",
            "device_id": None,
            "property": "temperature",
            "label": "Alter Sensor"
        },

        "humidity": {
            "source": "legacy",
            "device_id": None,
            "property": "humidity",
            "label": "Alter Sensor"
        }

    },

    # ================= DEVICE SYSTEM =================
    "DEVICE_MODES": {
        "fan":      {"mode": "ENV",  "params": {}},
        "vent":     {"mode": "TIME", "params": {}},
        "heating":  {"mode": "ENV",  "params": {}},
        "light":    {"mode": "ENV",  "params": {}}
    },

    "DEVICE_ENV_CONFIG": {
        "fan": {
            "use_temp": False,
            "use_hum": True,
            "logic": "OR",
            "direction": "HIGH"   # HIGH = bei zu hoher Temp/Hum an, LOW = bei zu niedriger Temp/Hum an
        },
        
        "vent": {
            "use_temp": False,
            "use_hum": False,
            "logic": "OR",
            "direction": "HIGH"
        }
    },

    # ================= ENERGY =================
    "ENERGY_RESET": {},
    "ENERGY_DAY_OFFSET": {},
    "ENERGY_DAY_RESET_MIN": 0,
    "ENERGY_LAST_DAY_RESET": None,

    # ================= SYSTEM =================
    "POWER_PRICE": 0.43,

    # ================= PLANTS =================
    "PLANTS": [{},{},{},{},{},{}]
}

# Fehlende Defaults ergänzen
for k, v in DEFAULT_CONFIG.items():
    config.setdefault(k, v)

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
