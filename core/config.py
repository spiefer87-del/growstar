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

    # Absolute Schutz-/Alarmgrenzen.
    "MIN_TEMP": 12.0,
    "MAX_TEMP": 30.0,
    "MIN_HUM": 0.0,
    "MAX_HUM": 75.0,

    # Benachrichtigungsabweichung relativ zum aktuell wirksamen Sollwert.
    # Diese Werte sind bewusst von DAY/NIGHT_*_TOL entkoppelt.
    "TEMP_ALERT_TOL": 5.0,
    "HUM_ALERT_TOL": 10.0,

    "TEMP_OFFSET": 0.0,
    "HUM_OFFSET": 0.0,

    "RAMP_DURATION_MIN": 60,
    "RAMP_ENABLED": 0,

    # ================= LICHT · SONNENVERLAUF =================
    "LIGHT_SUN_ENABLED": 0,
    "LIGHT_SUNRISE_DURATION_MIN": 30,
    "LIGHT_SUNSET_DURATION_MIN": 30,
    "LIGHT_SUN_MIN_LEVEL": 11,

    # ================= INTELLIGENTE VPD-STEUERUNG =================
    # OFF     = bisherige Klima-/ENV-Regelung unverändert
    # MONITOR = Entscheidungen und Wirkungstrends nur berechnen
    # AUTO    = ausschließlich Geräte im Modus ENV übernehmen
    "VPD_CONTROL_MODE": "OFF",
    "VPD_TARGET_DAY": 1.10,
    "VPD_TARGET_NIGHT": 0.90,
    "VPD_TOLERANCE": 0.05,

    # Erlaubtes Betriebsfenster der VPD-Optimierung. Die bestehenden
    # MIN_/MAX_-Werte bleiben davon getrennte Schutz-/Alarmgrenzen.
    "VPD_TEMP_MIN": 20.0,
    "VPD_TEMP_MAX": 28.0,
    "VPD_HUM_MIN": 40.0,
    "VPD_HUM_MAX": 70.0,

    # Eine Stufe wird erst nach fünf Minuten anhand des echten VPD-Trends
    # bewertet. Temperatur und Abluft werden nur in kleinen Schritten verändert.
    "VPD_EFFECT_WINDOW_MIN": 5,
    "VPD_MIN_EFFECT_KPA": 0.03,
    "VPD_TEMP_STEP": 0.5,
    "VPD_FAN_STEP": 10,

    "SENSOR_ASSIGNMENTS": {

        "temperature": {
            "source_id": "mqtt:ds18b20",
            "field": "temperature",
            "label": "Alter Temperatursensor"
        },

        "humidity": {
            "source_id": "mqtt:dht22",
            "field": "humidity",
            "label": "Alter Feuchtesensor"
        }

    },

    "SENSOR_UPDATE_INTERVAL_SEC": 60,

    # ================= DEVICE SYSTEM =================
    "DEVICE_MODES": {
        "fan":      {"mode": "ENV",  "params": {}},
        "vent":     {"mode": "TIME", "params": {}},
        "heating":  {"mode": "ENV",  "params": {}},
        "light":    {"mode": "ENV",  "params": {}},

        # Vier sichere Universal-Slots. Ohne Hardware-Zuordnung bleiben aktive
        # Modi zusätzlich durch den bestehenden Phase-4L-Guard blockiert.
        "aux1": "OFF",
        "aux2": "OFF",
        "aux3": "OFF",
        "aux4": "OFF"
    },

    "DEVICE_LABELS": {
        "aux1": "Wasserpumpen",
        "aux2": "Zusatzgerät 2",
        "aux3": "Zusatzgerät 3",
        "aux4": "Zusatzgerät 4"
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
