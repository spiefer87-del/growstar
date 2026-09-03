"""Stationsbezogene Safety-Bewertung fuer Growstar.

Dieses Modul ist absichtlich read-only gegenueber echter Hardware. Es wertet
nur Runtime-State, Sensor-Freshness, Geraetekonfiguration und den bereits vom
zentralen Hardware-Thread gepflegten Aktor-Health-Cache aus.

Physische Safe-Off-Aktionen werden ausschliesslich in services/safety.py
angestossen. Die letzte harte Barriere gegen ein erneutes Einschalten liegt
zusaetzlich in core.actuators.
"""

from __future__ import annotations

from copy import deepcopy
import time

from core.constants import SENSOR_TIMEOUT
from core.devices import DEVICE_NAMES, get_device_mode
from core.hardware.actuator_health import get_endpoint_health
from core.hardware_assignments import DEVICE_HARDWARE
from core.runtime import resolve_runtime


SAFETY_LOOP_MAX_AGE_SEC = 8.0
SAFETY_STATUS_STALE_SEC = 6.0
_ALLOWED_MODES = {"OFF", "ON", "TIME", "INTERVAL", "ENV"}


def _age(now, timestamp):
    try:
        timestamp = float(timestamp or 0)
    except (TypeError, ValueError):
        timestamp = 0.0
    if timestamp <= 0:
        return None
    return max(0.0, float(now) - timestamp)


def _sensor_health(runtime, sensor, *, now):
    st = runtime.state
    assignments = runtime.config.get("SENSOR_ASSIGNMENTS") or {}
    assignment = assignments.get(sensor) if isinstance(assignments, dict) else None
    if not isinstance(assignment, dict):
        assignment = {}

    if sensor == "temperature":
        timestamp = getattr(st, "last_ds_time", 0)
        stale_flag = bool(getattr(st, "temp_stale", False))
        value = st.live_state.get("temp")
    elif sensor == "humidity":
        timestamp = getattr(st, "last_dht_time", 0)
        stale_flag = bool(getattr(st, "hum_stale", False))
        value = st.live_state.get("hum")
    else:
        raise ValueError(f"Unbekannter Safety-Sensor: {sensor}")

    age = _age(now, timestamp)
    assigned = bool(str(assignment.get("source_id") or "").strip())
    fresh = bool(
        assigned
        and value is not None
        and not stale_flag
        and age is not None
        and age <= float(SENSOR_TIMEOUT)
    )

    return {
        "sensor": sensor,
        "assigned": assigned,
        "source_id": assignment.get("source_id"),
        "label": assignment.get("label") or assignment.get("source_id"),
        "value": value,
        "age": None if age is None else round(age, 1),
        "stale": not fresh,
        "ok": fresh,
        "max_age": float(SENSOR_TIMEOUT),
    }


def _device_dependencies(runtime, device, mode):
    """Nur ENV-Geraete besitzen Klima-Sensorabhaengigkeiten.

    Heizung und Profil-Licht haben historische Sonderlogik. Alle anderen
    ENV-Geraete verwenden DEVICE_ENV_CONFIG.
    """

    if mode != "ENV":
        return set()

    # Im VPD-AUTO-Modus beruhen alle koordinierten Entscheidungen auf dem
    # gemeinsamen Temperatur-/Feuchte-Paar. Der Safety-Supervisor darf daher
    # keinen dieser Aktoren bei nur teilweise frischen Innenwerten einschalten.
    vpd_control = runtime.state.live_state.get("vpd_control") or {}
    if (
        str(runtime.config.get("VPD_CONTROL_MODE", "OFF") or "OFF").upper()
        == "AUTO"
        and isinstance(vpd_control, dict)
        and bool(vpd_control.get("takeover"))
        and bool(vpd_control.get("ready"))
        and device in (vpd_control.get("managed_devices") or [])
    ):
        return {"temperature", "humidity"}

    if device == "heating":
        return {"temperature"}

    # ENV-Licht ist in Growstar Profil-/Zeitsteuerung und nicht klimaabhaengig.
    if device == "light":
        return set()

    env_root = runtime.config.get("DEVICE_ENV_CONFIG") or {}
    env = env_root.get(device) if isinstance(env_root, dict) else {}
    if not isinstance(env, dict):
        raise ValueError("DEVICE_ENV_CONFIG ist kein Objekt")
    required = set()
    if bool(env.get("use_temp")):
        required.add("temperature")
    if bool(env.get("use_hum")):
        required.add("humidity")
    return required


def _hardware_health(runtime, device, *, now):
    meta = DEVICE_HARDWARE.get(device)
    if meta is None:
        return {
            "configured": False,
            "ok": False,
            "state": "unknown",
            "reachable": None,
            "actual_state": None,
            "can_attempt_off": False,
            "ip": None,
            "relay": None,
            "reason": "Keine Hardware-Metadaten",
        }

    cfg = runtime.config
    host = str(cfg.get(meta["ip_key"]) or "").strip()
    relay = cfg.get(meta["relay_key"])

    if not host or relay in (None, ""):
        return {
            "configured": False,
            "ok": False,
            "state": "unconfigured",
            "reachable": None,
            "actual_state": None,
            "can_attempt_off": False,
            "ip": host or None,
            "relay": None,
            "reason": "keine Hardware-Zuordnung",
        }

    try:
        relay = int(relay)
    except (TypeError, ValueError):
        return {
            "configured": False,
            "ok": False,
            "state": "invalid",
            "reachable": None,
            "actual_state": None,
            "can_attempt_off": False,
            "ip": host,
            "relay": relay,
            "reason": "ungueltiges Relay",
        }

    health = get_endpoint_health(host, relay, now=now)
    if not health:
        return {
            "configured": True,
            "ok": False,
            "state": "unknown",
            "reachable": None,
            "actual_state": None,
            "can_attempt_off": False,
            "ip": host,
            "relay": relay,
            "reason": "noch kein Aktor-Health-Poll",
        }

    ok = bool(
        health.get("state") == "ok"
        and health.get("reachable") is True
        and isinstance(health.get("actual_state"), bool)
    )

    if ok:
        reason = None
    elif health.get("state") == "error":
        reason = health.get("last_error") or "Aktor nicht erreichbar"
    elif health.get("state") == "warn":
        reason = "Aktor-Health-Poll stale"
    else:
        reason = "Aktorzustand nicht verifiziert"

    return {
        "configured": True,
        "ok": ok,
        "state": health.get("state") or "unknown",
        "reachable": health.get("reachable"),
        "actual_state": health.get("actual_state"),
        # Auch ein inzwischen stale Poll kann noch einen zuletzt eindeutig
        # erreichbaren Endpunkt kennen. Bei einem unabhaengigen Sensor-/Loop-
        # Failsafe darf dann ein AUS-Versuch erfolgen; neue EIN-Befehle bleiben
        # wegen health["ok"] trotzdem blockiert.
        "can_attempt_off": health.get("reachable") is True,
        "ip": host,
        "relay": relay,
        "check_age": health.get("check_age"),
        "success_age": health.get("success_age"),
        "last_error": health.get("last_error"),
        "reason": reason,
    }


def evaluate_runtime_safety(runtime=None, *, now=None):
    """Berechnet die Safety-Matrix genau einer Runtime ohne Netzwerkzugriff."""

    rt = resolve_runtime(runtime)
    now = time.time() if now is None else float(now)

    live = bool(rt.enabled and rt.control_enabled and not getattr(rt, "disarming", False))
    loop_age = _age(now, getattr(rt, "last_loop_ts", None))
    loop_ok = bool(loop_age is not None and loop_age <= SAFETY_LOOP_MAX_AGE_SEC)

    sensors = {
        "temperature": _sensor_health(rt, "temperature", now=now),
        "humidity": _sensor_health(rt, "humidity", now=now),
    }

    if not live:
        return {
            "tent_id": rt.tent_id,
            "checked_ts": now,
            "state": "inactive",
            "active": False,
            "live": False,
            "stale": False,
            "loop": {
                "ok": loop_ok,
                "age": None if loop_age is None else round(loop_age, 1),
                "max_age": SAFETY_LOOP_MAX_AGE_SEC,
            },
            "sensors": sensors,
            "devices": {},
            "overrides": {},
            "blocked_devices": [],
            "reason": None,
        }

    devices = {}
    overrides = {}
    blocked_devices = []

    for device in DEVICE_NAMES:
        try:
            mode = str(get_device_mode(device, runtime=rt) or "OFF").upper()
        except Exception:
            mode = "INVALID"

        active = mode != "OFF"
        if not active:
            devices[device] = {
                "mode": mode,
                "active": False,
                "dependencies": [],
                "blocked": False,
                "force_off": False,
                "block_on": False,
                "reasons": [],
            }
            continue

        reasons = []
        force_off = False
        block_on = False

        if mode not in _ALLOWED_MODES:
            reasons.append(f"ungueltiger Geraetemodus {mode}")
            force_off = True
            block_on = True

        try:
            dependencies = _device_dependencies(rt, device, mode)
        except Exception as exc:
            dependencies = set()
            reasons.append(f"ENV-Konfiguration ungueltig: {exc}")
            force_off = True
            block_on = True

        if not loop_ok:
            reasons.append("Regelkreis-Heartbeat stale")
            force_off = True
            block_on = True

        for sensor in sorted(dependencies):
            if not sensors[sensor]["ok"]:
                label = "Temperatursensor" if sensor == "temperature" else "Feuchtesensor"
                reasons.append(f"{label} stale/nicht verfuegbar")
                force_off = True
                block_on = True

        hardware = _hardware_health(rt, device, now=now)
        if not hardware["ok"]:
            reasons.append(
                "Hardware nicht sicher verifiziert: "
                + str(hardware.get("reason") or hardware.get("state") or "unbekannt")
            )
            # Bei einem nicht verifizierten Endpunkt darf kein neuer EIN-Befehl
            # entstehen. Ein Safe-Off wird erst aktiv gesendet, wenn der zentrale
            # Health-Cache den Endpunkt wieder als erreichbar bestaetigt.
            block_on = True

        blocked = bool(force_off or block_on)
        if blocked:
            blocked_devices.append(device)
            overrides[device] = {
                "force_off": bool(force_off),
                "block_on": bool(block_on),
                "can_attempt_off": bool(hardware.get("can_attempt_off")),
                "reason": "; ".join(reasons),
                "reasons": list(reasons),
            }

        devices[device] = {
            "mode": mode,
            "active": True,
            "dependencies": sorted(dependencies),
            "blocked": blocked,
            "force_off": bool(force_off),
            "block_on": bool(block_on),
            "reasons": reasons,
            "hardware": hardware,
        }

    active_safety = bool(blocked_devices)
    summary = None
    if active_safety:
        summary = ", ".join(
            f"{device}: {overrides[device]['reason']}"
            for device in blocked_devices
        )

    return {
        "tent_id": rt.tent_id,
        "checked_ts": now,
        "state": "error" if active_safety else "ok",
        "active": active_safety,
        "live": True,
        "stale": False,
        "loop": {
            "ok": loop_ok,
            "age": None if loop_age is None else round(loop_age, 1),
            "max_age": SAFETY_LOOP_MAX_AGE_SEC,
        },
        "sensors": sensors,
        "devices": devices,
        "overrides": overrides,
        "blocked_devices": blocked_devices,
        "reason": summary,
    }


def emergency_runtime_safety(runtime=None, *, reason, now=None):
    """Fail-closed Snapshot, falls die normale Safety-Auswertung selbst fehlschlaegt.

    Alle nicht explizit OFF gesetzten Geraete werden mindestens gegen neue
    EIN-Befehle gesperrt. Ist ihr zentraler Hardware-Health-Cache noch gesund,
    kann services/safety.py einen bereits laufenden Aktor zusaetzlich sicher
    ausschalten.
    """

    rt = resolve_runtime(runtime)
    now = time.time() if now is None else float(now)
    text = f"Safety-Auswertung fehlgeschlagen: {reason}"
    devices = {}
    overrides = {}
    blocked = []

    for device in DEVICE_NAMES:
        try:
            mode = str(get_device_mode(device, runtime=rt) or "OFF").upper()
        except Exception:
            mode = "INVALID"

        if mode == "OFF":
            devices[device] = {
                "mode": mode,
                "active": False,
                "blocked": False,
                "force_off": False,
                "block_on": False,
                "reasons": [],
            }
            continue

        try:
            hardware = _hardware_health(rt, device, now=now)
            can_attempt_off = bool(hardware.get("can_attempt_off"))
        except Exception:
            hardware = {"ok": False, "state": "unknown", "can_attempt_off": False}
            can_attempt_off = False

        blocked.append(device)
        overrides[device] = {
            "force_off": True,
            "block_on": True,
            "can_attempt_off": can_attempt_off,
            "reason": text,
            "reasons": [text],
        }
        devices[device] = {
            "mode": mode,
            "active": True,
            "dependencies": [],
            "blocked": True,
            "force_off": True,
            "block_on": True,
            "reasons": [text],
            "hardware": hardware,
        }

    return {
        "tent_id": rt.tent_id,
        "checked_ts": now,
        "state": "error",
        "active": True,
        "live": bool(rt.control_enabled),
        "stale": False,
        "loop": {},
        "sensors": {},
        "devices": devices,
        "overrides": overrides,
        "blocked_devices": blocked,
        "reason": text,
    }


def store_runtime_safety(runtime, snapshot):
    rt = resolve_runtime(runtime)
    snapshot = deepcopy(snapshot or {})
    overrides = deepcopy(snapshot.get("overrides") or {})

    lock = getattr(rt, "safety_lock", None)
    if lock is None:
        rt.safety_status = snapshot
        rt.safety_overrides = overrides
        rt.last_safety_ts = snapshot.get("checked_ts") or time.time()
        return

    with lock:
        rt.safety_status = snapshot
        rt.safety_overrides = overrides
        rt.last_safety_ts = snapshot.get("checked_ts") or time.time()


def clear_runtime_safety(runtime, *, reason=None, now=None):
    rt = resolve_runtime(runtime)
    now = time.time() if now is None else float(now)
    snapshot = {
        "tent_id": rt.tent_id,
        "checked_ts": now,
        "state": "inactive",
        "active": False,
        "live": False,
        "stale": False,
        "loop": {},
        "sensors": {},
        "devices": {},
        "overrides": {},
        "blocked_devices": [],
        "reason": reason,
    }
    store_runtime_safety(rt, snapshot)
    return snapshot


def get_runtime_safety_snapshot(runtime=None, *, now=None):
    """Liefert nur gespeicherten Supervisor-Status; keine Hardwareaktionen."""

    rt = resolve_runtime(runtime)
    now = time.time() if now is None else float(now)
    lock = getattr(rt, "safety_lock", None)

    if lock is None:
        snapshot = deepcopy(getattr(rt, "safety_status", None))
    else:
        with lock:
            snapshot = deepcopy(getattr(rt, "safety_status", None))

    if not snapshot:
        snapshot = {
            "tent_id": rt.tent_id,
            "checked_ts": None,
            "state": "unknown" if rt.control_enabled else "inactive",
            "active": False,
            "live": bool(rt.control_enabled),
            "stale": bool(rt.control_enabled),
            "devices": {},
            "overrides": {},
            "blocked_devices": [],
            "reason": "Safety Supervisor noch ohne Status" if rt.control_enabled else None,
        }

    age = _age(now, snapshot.get("checked_ts"))
    stale = bool(rt.control_enabled and (age is None or age > SAFETY_STATUS_STALE_SEC))
    snapshot["age"] = None if age is None else round(age, 1)
    snapshot["stale_after"] = SAFETY_STATUS_STALE_SEC
    snapshot["stale"] = stale

    if stale:
        snapshot["state"] = "error"
        snapshot["active"] = True
        snapshot["reason"] = "Safety Supervisor Heartbeat stale"

    return snapshot
