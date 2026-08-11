# core/actuators.py

import requests

from core.runtime import resolve_runtime


def switch_shelly(ip, relay, enabled, timeout=3):
    relay = int(relay)

    # =========================
    # Gen2 / Pro API
    # =========================
    try:
        url = f"http://{ip}/rpc/Switch.Set"
        payload = {
            "id": relay,
            "on": bool(enabled),
        }

        response = requests.post(url, json=payload, timeout=timeout)
        if response.status_code == 200:
            return True

    except Exception:
        pass

    # =========================
    # Gen1 Fallback
    # =========================
    try:
        url = f"http://{ip}/relay/{relay}?turn={'on' if enabled else 'off'}"
        response = requests.get(url, timeout=timeout)

        if response.status_code == 200:
            return True

    except Exception as exc:
        print(f"❌ Shelly Fehler {ip} Relay {relay}:", exc)

    return False


def get_shelly_relay_state(ip, relay, timeout=3):
    relay = int(relay)

    # ---------- Gen2 / Strip / Pro ----------
    try:
        url = f"http://{ip}/rpc/Switch.GetStatus?id={relay}"
        response = requests.get(url, timeout=timeout)

        if response.status_code != 200:
            return None

        data = response.json()
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
        response = requests.get(url, timeout=timeout)

        if response.status_code != 200:
            return None

        data = response.json()
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

def _set_shelly_device(
    *,
    enabled,
    state_attr,
    live_key,
    ip_key,
    relay_key,
    on_text,
    off_text,
    reason="",
    runtime=None,
):
    rt = resolve_runtime(runtime)
    st = rt.state
    cfg = rt.config

    # -------------------------------------------------
    # Phase 3B: harte Shadow-Sicherheitsbarriere
    # -------------------------------------------------
    # Zusätzliche Zelte dürfen bereits denselben Regelalgorithmus ausführen,
    # aber solange control_enabled=False ist, darf diese Funktion NIEMALS
    # einen Netzwerk-Schaltbefehl senden. Der berechnete Sollzustand wird
    # getrennt vom realen Relaiszustand in shadow_outputs protokolliert.
    if not rt.control_enabled or getattr(rt, "disarming", False):
        desired = bool(enabled)

        with rt.state_lock:
            previous = rt.shadow_outputs.get(live_key)
            rt.shadow_outputs[live_key] = desired

        if previous != desired:
            print(
                f"🧪 [{rt.tent_id}] SHADOW {live_key}: "
                f"{'EIN' if desired else 'AUS'} {reason}"
            )
        return

    # -------------------------------------------------
    # Phase 4I: harte stationsbezogene Safety-Barriere
    # -------------------------------------------------
    # Der unabhaengige Safety-Supervisor schreibt nur Runtime-Overrides.
    # Hier liegt die letzte Barriere direkt vor jedem realen Shelly-Befehl:
    # - block_on verhindert neue EIN-Befehle bei unverifizierter Hardware.
    # - force_off verwandelt einen angeforderten EIN-Zustand in AUS, z.B. bei
    #   stale Sensor oder stale Regelkreis.
    safety_lock = getattr(rt, "safety_lock", None)
    if safety_lock is None:
        override = dict((getattr(rt, "safety_overrides", {}) or {}).get(live_key) or {})
    else:
        with safety_lock:
            override = dict((getattr(rt, "safety_overrides", {}) or {}).get(live_key) or {})

    requested_enabled = bool(enabled)
    if requested_enabled and override.get("force_off"):
        # Ist der Endpunkt aktuell nicht sicher erreichbar, darf hier weder
        # ein EIN- noch ein wiederholter AUS-Request erzeugt werden. Der
        # Override bleibt bestehen; services/safety.py schaltet AUS, sobald
        # der zentrale Health-Cache Hardware wieder als erreichbar meldet.
        if not override.get("can_attempt_off"):
            return
        enabled = False
        safety_reason = override.get("reason") or "Safety-Failsafe"
        reason = f"{reason} (SAFETY: {safety_reason})"
    elif requested_enabled and override.get("block_on"):
        # Hardware-/Konfigurationsproblem: kein neuer EIN-Befehl. AUS bleibt
        # weiterhin erlaubt, damit ein normaler Safe-Off nicht blockiert wird.
        return

    if enabled == getattr(st, state_attr):
        return

    ip = cfg.get(ip_key)
    relay = cfg.get(relay_key)

    if not ip or relay is None:
        # Bestehendes Verhalten war bei vollständiger Config ein normaler
        # Shelly-Aufruf. Bei einer zukünftigen, noch unvollständigen Zelt-
        # Config verhindern wir hier bewusst einen Request auf "None".
        return

    if not switch_shelly(ip, relay, enabled):
        return

    setattr(st, state_attr, enabled)
    st.live_state[live_key] = enabled
    print((on_text if enabled else off_text) + reason + f" [{rt.tent_id}]")


def set_heating(enabled, reason="", runtime=None):
    _set_shelly_device(
        enabled=enabled,
        state_attr="heating_on",
        live_key="heating",
        ip_key="IP_HEATING",
        relay_key="RELAY_HEATING",
        on_text="🔥 HEIZUNG EIN ",
        off_text="❄️ HEIZUNG AUS ",
        reason=reason,
        runtime=runtime,
    )


def set_fan(enabled, reason="", runtime=None):
    _set_shelly_device(
        enabled=enabled,
        state_attr="fan_on",
        live_key="fan",
        ip_key="IP_FAN",
        relay_key="RELAY_FAN",
        on_text="💨 UMLUFT EIN ",
        off_text="🛑 UMLUFT AUS ",
        reason=reason,
        runtime=runtime,
    )


def set_light(enabled, reason="", runtime=None):
    _set_shelly_device(
        enabled=enabled,
        state_attr="light_on",
        live_key="light",
        ip_key="IP_LIGHT",
        relay_key="RELAY_LIGHT",
        on_text="💡 LICHT EIN ",
        off_text="🛑 LICHT AUS ",
        reason=reason,
        runtime=runtime,
    )


def set_vent(enabled, reason="", runtime=None):
    _set_shelly_device(
        enabled=enabled,
        state_attr="vent_on",
        live_key="vent",
        ip_key="IP_VENT",
        relay_key="RELAY_VENT",
        on_text="🌀 VENTILATOR EIN ",
        off_text="🛑 VENTILATOR AUS ",
        reason=reason,
        runtime=runtime,
    )


def set_irrigation(enabled, reason="", runtime=None):
    _set_shelly_device(
        enabled=enabled,
        state_attr="irrigation_on",
        live_key="irrigation",
        ip_key="IP_IRRIGATION",
        relay_key="RELAY_IRRIGATION",
        on_text="🚿 BEWÄSSERUNG EIN ",
        off_text="🛑 BEWÄSSERUNG AUS ",
        reason=reason,
        runtime=runtime,
    )


def set_humidifier(enabled, reason="", runtime=None):
    _set_shelly_device(
        enabled=enabled,
        state_attr="humidifier_on",
        live_key="humidifier",
        ip_key="IP_HUMIDIFIER",
        relay_key="RELAY_HUMIDIFIER",
        on_text="💧 LUFTBEFEUCHTER EIN ",
        off_text="🛑 LUFTBEFEUCHTER AUS ",
        reason=reason,
        runtime=runtime,
    )


def set_dehumidifier(enabled, reason="", runtime=None):
    _set_shelly_device(
        enabled=enabled,
        state_attr="dehumidifier_on",
        live_key="dehumidifier",
        ip_key="IP_DEHUMIDIFIER",
        relay_key="RELAY_DEHUMIDIFIER",
        on_text="💨 LUFTENTFEUCHTER EIN ",
        off_text="🛑 LUFTENTFEUCHTER AUS ",
        reason=reason,
        runtime=runtime,
    )


def set_light2(enabled, reason="", runtime=None):
    _set_shelly_device(
        enabled=enabled,
        state_attr="light2_on",
        live_key="light2",
        ip_key="IP_LIGHT2",
        relay_key="RELAY_LIGHT2",
        on_text="💡 LIGHT2 EIN ",
        off_text="🛑 LIGHT2 AUS ",
        reason=reason,
        runtime=runtime,
    )


def set_vent2(enabled, reason="", runtime=None):
    _set_shelly_device(
        enabled=enabled,
        state_attr="vent2_on",
        live_key="vent2",
        ip_key="IP_VENT2",
        relay_key="RELAY_VENT2",
        on_text="🌀 VENT2 EIN ",
        off_text="🛑 VENT2 AUS ",
        reason=reason,
        runtime=runtime,
    )


# =========================================
# 🔌 DEVICE SETTER MAPPING
# =========================================

DEVICE_SETTERS = {
    "fan": set_fan,
    "vent": set_vent,
    "heating": set_heating,
    "light": set_light,
    "light2": set_light2,
    "vent2": set_vent2,
    "irrigation": set_irrigation,
    "humidifier": set_humidifier,
    "dehumidifier": set_dehumidifier,
}


def set_device(device, enabled, runtime=None, reason=""):
    setter = DEVICE_SETTERS.get(device)
    if setter:
        setter(enabled, reason=reason, runtime=runtime)
