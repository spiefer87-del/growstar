import datetime
import requests

import core.context as ctx

from core.constants import ENERGY_DEVICES
from core.config import config, save_config

def do_energy_day_reset():
    """
    Setzt für ALLE Geräte den Tages-Offset auf den aktuellen Rohwert.
    Ergebnis: today = 0.0 für alle Geräte.
    """
    today_str = datetime.date.today().isoformat()

    config.setdefault("ENERGY_DAY_OFFSET", {})

    with ctx.energy_lock:
        snapshot = dict(ctx.energy_state)

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

    with ctx.energy_lock:
        ctx.energy_state.clear()
    
        for name, (ip_k, r_k) in ENERGY_DEVICES.items():
            ip = config.get(ip_k)
            relay = config.get(r_k)
    
            if not ip or relay is None:
                continue
    
            e = get_shelly_energy(ip, relay, name)
            if e:
                ctx.energy_state[name] = e


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
