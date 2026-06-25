#core/actuators.py

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

# =========================================
# 🔥 AKTOREN
# =========================================
def set_heating(enabled, reason=""):

    if enabled == state.heating_on:
        return

    if not switch_shelly(
        config.get("IP_HEATING"),
        config.get("RELAY_HEATING"),
        enabled
    ):
        return

    state.heating_on = enabled
    state.live_state["heating"] = enabled
    print(("🔥 HEIZUNG EIN " if enabled else "❄️ HEIZUNG AUS ") + reason)

def set_fan(enabled, reason=""):

    if enabled == state.fan_on:
        return
    
    if not switch_shelly(
        config.get("IP_FAN"),
        config.get("RELAY_FAN"),
        enabled
    ):
        return

    state.fan_on = enabled
    state.live_state["fan"] = enabled
    print(("💨 UMLUFT EIN " if enabled else "🛑 UMLUFT AUS ") + reason)

def set_light(enabled, reason=""):

    if enabled == state.light_on:
        return
    
    if not switch_shelly(
        config.get("IP_LIGHT"),
        config.get("RELAY_LIGHT"),
        enabled
    ):
        return

    state.light_on = enabled
    state.live_state["light"] = enabled
    print(("💡 LICHT EIN " if enabled else "🛑 LICHT AUS ") + reason)

def set_vent(enabled, reason=""):

    if enabled == state.vent_on:
        return
    
    if not switch_shelly(
        config.get("IP_VENT"),
        config.get("RELAY_VENT"),
        enabled
    ):
        return

    state.vent_on = enabled
    state.live_state["vent"] = enabled
    print(("🌀 VENTILATOR EIN " if enabled else "🛑 VENTILATOR AUS ") + reason)

def set_irrigation(enabled, reason=""):

    if enabled == state.irrigation_on:
        return
    
    if not switch_shelly(
        config.get("IP_IRRIGATION"),
        config.get("RELAY_IRRIGATION"),
        enabled
    ):
        return
            
    state.irrigation_on = enabled
    state.live_state["irrigation"] = enabled
    print(("🚿 BEWÄSSERUNG EIN " if enabled else "🛑 BEWÄSSERUNG AUS ") + reason)

def set_humidifier(enabled, reason=""):

    if enabled == state.humidifier_on:
        return
    
    if not switch_shelly(
        config.get("IP_HUMIDIFIER"),
        config.get("RELAY_HUMIDIFIER"),
        enabled
    ):
        return
            
    state.humidifier_on = enabled
    state.live_state["humidifier"] = enabled
    print(("💧 LUFTBEFEUCHTER EIN " if enabled else "🛑 LUFTBEFEUCHTER AUS ") + reason)

def set_dehumidifier(enabled, reason=""):

    if enabled == state.dehumidifier_on:
        return
    
    if not switch_shelly(
        config.get("IP_DEHUMIDIFIER"),
        config.get("RELAY_DEHUMIDIFIER"),
        enabled
    ):
        return
            
    state.dehumidifier_on = enabled
    state.live_state["dehumidifier"] = enabled
    print(("💨 LUFTENTFEUCHTER EIN " if enabled else "🛑 LUFTENTFEUCHTER AUS ") + reason)

def set_light2(enabled, reason=""):

    if enabled == state.light2_on:
        return
    
    if not switch_shelly(
        config.get("IP_LIGHT2"),
        config.get("RELAY_LIGHT2"),
        enabled
    ):
        return
            
    state.light2_on = enabled
    state.live_state["light2"] = enabled
    print(("💡 LIGHT2 EIN " if enabled else "🛑 LIGHT2 AUS ") + reason)

def set_vent2(enabled, reason=""):

    if enabled == state.vent2_on:
        return
    
    if not switch_shelly(
        config.get("IP_VENT2"),
        config.get("RELAY_VENT2"),
        enabled
    ):
        return
            
    state.vent2_on = enabled
    state.live_state["vent2"] = enabled
    print(("🌀 VENT2 EIN " if enabled else "🛑 VENT2 AUS ") + reason)

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

def set_device(device, state):
    setter = DEVICE_SETTERS.get(device)
    if setter:
        setter(state)
