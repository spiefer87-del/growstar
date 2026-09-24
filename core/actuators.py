# core/actuators.py

import requests
import time
import uuid

import core.context as ctx

from core.runtime import resolve_runtime


_ACTUATOR_EVENT_SESSION_ID = uuid.uuid4().hex[:12]


def _rounded_event_value(value, digits=2):
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _interval_relay_strategy(params, profile):
    params = params if isinstance(params, dict) else {}
    states = params.get("control_states")
    states = states if isinstance(states, dict) else {}

    def power(name, fallback):
        state = states.get(name)
        if not isinstance(state, dict):
            return bool(fallback)
        return bool(state.get("power", fallback))

    day_a = power("interval_a", True)
    day_b = power("interval_b", False)
    use_night = bool(params.get("interval_night_enabled")) and profile == "NACHT"
    phase_a = power("interval_a_night", day_a) if use_night else day_a
    phase_b = power("interval_b_night", day_b) if use_night else day_b
    if phase_a and phase_b:
        strategy = "INTERVALL_DAUERSTROM"
    elif phase_a or phase_b:
        strategy = "INTERVALL_SCHALTEND"
    else:
        strategy = "INTERVALL_AUS"
    return {
        "relaisstrategie": strategy,
        "phase_a_power": "EIN" if phase_a else "AUS",
        "phase_b_power": "EIN" if phase_b else "AUS",
        "intervallprofil": "NACHT" if use_night else "TAG",
    }


def _actuator_event_context(runtime, device, mode):
    """Liest einen konsistenten, rein diagnostischen Klima-Snapshot."""
    st = runtime.state
    cfg = runtime.config
    with runtime.state_lock:
        live = dict(st.live_state or {})
        vpd_control = dict(live.get("vpd_control") or {})

    profile = str(
        live.get("profile") or getattr(st, "current_profile", None) or ""
    ).upper() or None
    temperature = _rounded_event_value(live.get("temp"))
    humidity = _rounded_event_value(live.get("hum"))
    vpd = _rounded_event_value(live.get("vpd"), 3)
    temp_target = _rounded_event_value(live.get("temp_target"))
    temp_tolerance = _rounded_event_value(live.get("temp_tol"))
    hum_target = _rounded_event_value(live.get("hum_target"))
    hum_tolerance = _rounded_event_value(live.get("hum_tol"))

    context = {
        "sitzung": _ACTUATOR_EVENT_SESSION_ID,
        "profil": profile,
        "temperatur_c": temperature,
        "luftfeuchte_pct": humidity,
        "vpd_kpa": vpd,
        "temperatur_soll_c": temp_target,
        "temperatur_toleranz_c": temp_tolerance,
        "feuchte_soll_pct": hum_target,
        "feuchte_toleranz_pct": hum_tolerance,
        "vpd_modus": str(
            vpd_control.get("mode") or cfg.get("VPD_CONTROL_MODE") or "OFF"
        ).upper(),
    }
    if mode == "ON":
        context["relaisstrategie"] = "DAUERBETRIEB"
    elif mode == "INTERVAL":
        try:
            from core.devices import get_device_params

            context.update(_interval_relay_strategy(
                get_device_params(device, runtime=runtime),
                profile,
            ))
        except Exception:
            context["relaisstrategie"] = "INTERVALL_UNBEKANNT"
    elif mode == "TIME":
        context["relaisstrategie"] = "ZEITPLAN"
    elif mode == "TIMER":
        context["relaisstrategie"] = "ZEITSCHALTUHR"
    elif mode == "ENV":
        context["relaisstrategie"] = "BEDARFSGESTEUERT"
    if temperature is not None and temp_target is not None:
        context["temperatur_abweichung_c"] = round(temperature - temp_target, 2)
    if humidity is not None and hum_target is not None:
        context["feuchte_abweichung_pct"] = round(humidity - hum_target, 2)
    return {key: value for key, value in context.items() if value is not None}


def _enqueue_actuator_transition(runtime, device, enabled, reason=""):
    """Protokolliert nur einen tatsaechlich angenommenen Relaiswechsel."""
    try:
        from core.devices import get_device_label, get_device_mode
        from services.grow_events import enqueue_event

        label = get_device_label(device, runtime=runtime)
        state_label = "eingeschaltet" if enabled else "ausgeschaltet"
        clean_reason = " ".join(str(reason or "").strip(" ()").split())[:300]
        mode = get_device_mode(device, runtime=runtime)
        summary = (
            f"Growstar hat {label} {state_label}."
            + (f" Grund: {clean_reason}." if clean_reason else "")
        )
        occurred_at = int(time.time())
        metadata = {
            "geraet": str(device),
            "zustand": "EIN" if enabled else "AUS",
            "modus": mode,
            "grund": clean_reason or None,
        }
        metadata.update(_actuator_event_context(runtime, device, mode))
        enqueue_event(
            station_id=runtime.tent_id,
            occurred_at=occurred_at,
            category="device",
            event_type="actuator_power_changed",
            severity="info",
            title=f"{label} {state_label}",
            summary=summary,
            source="actuator_control",
            source_id=str(device),
            dedupe_key=(
                f"actuator:{runtime.tent_id}:{device}:"
                f"{'on' if enabled else 'off'}:{time.time_ns()}"
            ),
            metadata=metadata,
        )
    except Exception as exc:
        # Die Timeline darf einen erfolgreichen Hardwarepfad nie beeinflussen.
        print("⚠️ Aktorwechsel konnte nicht an Grow Intelligence übergeben werden:", exc)


def _request_error(stage, exc, timeout):
    """Klassifiziert Shelly-Transportfehler für Health/Safety-Diagnosen."""

    if isinstance(exc, requests.Timeout):
        return f"{stage}: Timeout nach {float(timeout):.1f}s"

    if isinstance(exc, requests.ConnectionError):
        return f"{stage}: Verbindungsfehler: {exc}"

    if isinstance(exc, requests.RequestException):
        return f"{stage}: Netzwerkfehler: {exc}"

    return f"{stage}: unerwarteter Fehler: {exc}"


def switch_shelly(ip, relay, enabled, timeout=3):
    relay = int(relay)

    # Phase 4V.4:
    # Eine komplette Relay-Schaltoperation (Gen2 + möglicher Gen1-Fallback)
    # bleibt gegenüber allen anderen regulären Shelly-HTTP-Zugriffen atomar.
    with ctx.shelly_lock:

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


def probe_shelly_relay_state(ip, relay, timeout=3):
    """Liest einen Relay-Status read-only und liefert einen Diagnose-Datensatz.

    Rückgabe:
        {
            "reachable": bool,
            "actual_state": bool | None,
            "error": str | None,
            "protocol": "gen2" | "gen1" | None,
        }

    Die bestehende öffentliche Funktion get_shelly_relay_state() bleibt als
    bool/None-Wrapper erhalten, damit ältere Aufrufer unverändert funktionieren.
    """

    relay = int(relay)
    errors = []

    # Eine komplette Statusermittlung bleibt gegenüber anderen regulären
    # Shelly-HTTP-Requests atomar. Das verhindert insbesondere Kollisionen
    # zwischen BLE/Inventar-RPC und dem Safety-relevanten Aktor-Health.
    with ctx.shelly_lock:

        # ---------- Gen2 / Strip / Pro ----------
        try:
            url = f"http://{ip}/rpc/Switch.GetStatus?id={relay}"
            response = requests.get(url, timeout=timeout)

            if response.status_code != 200:
                errors.append(f"Gen2: HTTP {response.status_code}")
            else:
                try:
                    data = response.json()
                except ValueError as exc:
                    errors.append(f"Gen2: ungültiges JSON: {exc}")
                else:
                    if not isinstance(data, dict):
                        errors.append("Gen2: JSON-Antwort ist kein Objekt")
                    elif "output" not in data:
                        errors.append("Gen2: Feld 'output' fehlt")
                    elif not isinstance(data["output"], bool):
                        errors.append("Gen2: Feld 'output' ist kein bool")
                    else:
                        return {
                            "reachable": True,
                            "actual_state": data["output"],
                            "error": None,
                            "protocol": "gen2",
                        }

        except Exception as exc:
            errors.append(_request_error("Gen2", exc, timeout))

        # ---------- Gen1 Fallback ----------
        try:
            url = f"http://{ip}/status"
            response = requests.get(url, timeout=timeout)

            if response.status_code != 200:
                errors.append(f"Gen1: HTTP {response.status_code}")
            else:
                try:
                    data = response.json()
                except ValueError as exc:
                    errors.append(f"Gen1: ungültiges JSON: {exc}")
                else:
                    relays = data.get("relays") if isinstance(data, dict) else None

                    if not isinstance(relays, list):
                        errors.append("Gen1: Feld 'relays' fehlt/ist ungültig")
                    elif relay < 0 or relay >= len(relays):
                        errors.append(
                            f"Gen1: Relay {relay} außerhalb des gültigen Bereichs"
                        )
                    else:
                        raw_state = relays[relay].get("ison")
                        if not isinstance(raw_state, bool):
                            errors.append("Gen1: Feld 'ison' ist kein bool")
                        else:
                            return {
                                "reachable": True,
                                "actual_state": raw_state,
                                "error": None,
                                "protocol": "gen1",
                            }

        except Exception as exc:
            errors.append(_request_error("Gen1", exc, timeout))

    return {
        "reachable": False,
        "actual_state": None,
        "error": " | ".join(errors) or "Keine verwertbare Shelly-Antwort",
        "protocol": None,
    }


def get_shelly_relay_state(ip, relay, timeout=3):
    result = probe_shelly_relay_state(
        ip,
        relay,
        timeout=timeout,
    )

    if result.get("reachable") and isinstance(result.get("actual_state"), bool):
        return result["actual_state"]

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
    _enqueue_actuator_transition(rt, live_key, bool(enabled), reason)


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


_AUX_DEVICE_NAMES = ("aux1", "aux2", "aux3", "aux4")
_AUX_DEFAULT_LABELS = {
    "aux1": "Wasserpumpen",
    "aux2": "Zusatzgerät 2",
    "aux3": "Zusatzgerät 3",
    "aux4": "Zusatzgerät 4",
}
_AUX_ICONS = {
    "aux1": "💧",
    "aux2": "🔌",
    "aux3": "🔌",
    "aux4": "🔌",
}


def _aux_display_label(runtime, device):
    labels = runtime.config.get("DEVICE_LABELS") or {}
    label = labels.get(device) if isinstance(labels, dict) else None
    label = " ".join(str(label or "").split()).strip()
    return label or _AUX_DEFAULT_LABELS[device]


def set_auxiliary(device, enabled, reason="", runtime=None):
    """Schaltet einen freien Universal-Aktor über denselben Shelly-/Safety-Pfad."""
    if device not in _AUX_DEVICE_NAMES:
        raise ValueError(f"Unbekannter Universal-Aktor: {device}")

    rt = resolve_runtime(runtime)
    suffix = device.upper()
    label = _aux_display_label(rt, device)
    icon = _AUX_ICONS[device]

    _set_shelly_device(
        enabled=enabled,
        state_attr=f"{device}_on",
        live_key=device,
        ip_key=f"IP_{suffix}",
        relay_key=f"RELAY_{suffix}",
        on_text=f"{icon} {label} EIN ",
        off_text=f"🛑 {label} AUS ",
        reason=reason,
        runtime=rt,
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
        return

    if device in _AUX_DEVICE_NAMES:
        set_auxiliary(
            device,
            enabled,
            reason=reason,
            runtime=runtime,
        )
