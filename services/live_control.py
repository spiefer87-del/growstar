"""Controlled SHADOW <-> LIVE transitions for additional local stations."""

from __future__ import annotations

import threading
import time

from core.actuators import get_shelly_relay_state, switch_shelly
from core.hardware.actuator_health import get_endpoint_health
from core.hardware_assignments import DEVICE_HARDWARE
from core.live_preflight import evaluate_live_preflight
from core.runtime import get_runtime, list_runtimes, resolve_runtime
from core.tents import DEFAULT_TENT_ID, manager as tent_manager, validate_tent_id


ARMING_RETRY_SEC = 5
_transition_lock = threading.RLock()


class LiveTransitionError(RuntimeError):
    def __init__(self, message, *, preflight=None, code="live_transition_failed"):
        super().__init__(message)
        self.preflight = preflight
        self.code = code


def _set_runtime_device_state(runtime, device, value):
    if not isinstance(value, bool):
        return
    with runtime.state_lock:
        setattr(runtime.state, f"{device}_on", value)
        runtime.state.live_state[device] = value


def seed_runtime_from_health(runtime=None):
    """Seeds real relay state from the central read-only health cache."""

    rt = resolve_runtime(runtime)
    seeded = []

    for device, meta in DEVICE_HARDWARE.items():
        host = str(rt.config.get(meta["ip_key"]) or "").strip()
        relay = rt.config.get(meta["relay_key"])
        if not host or relay in (None, ""):
            continue

        try:
            relay = int(relay)
        except (TypeError, ValueError):
            continue

        health = get_endpoint_health(host, relay)
        if not health or health.get("state") != "ok":
            continue
        actual = health.get("actual_state")
        if not isinstance(actual, bool):
            continue

        _set_runtime_device_state(rt, device, actual)
        seeded.append({"device": device, "state": actual})

    return seeded


def _persist_live_metadata(runtime, *, live):
    if runtime.tent_id == DEFAULT_TENT_ID:
        return tent_manager.get(DEFAULT_TENT_ID)

    return tent_manager.set_control_enabled(
        runtime.tent_id,
        bool(live),
        shadow_when_disabled=not bool(live),
    )


def _activate_runtime(runtime, *, persist):
    rt = resolve_runtime(runtime)

    preflight = evaluate_live_preflight(rt)
    rt.last_live_preflight = preflight
    if not preflight["ready"]:
        rt.arming = bool(getattr(rt, "live_requested", False))
        raise LiveTransitionError(
            "LIVE-Preflight nicht erfüllt",
            preflight=preflight,
            code="live_preflight_failed",
        )

    # Important ordering:
    # 1) seed the known real relay states while the hardware gate is CLOSED;
    # 2) persist the requested LIVE target (if this is an explicit user action);
    # 3) only then open the in-process hardware gate.
    # If persistence fails, no hardware can have been enabled yet.
    seed_runtime_from_health(rt)

    if persist:
        _persist_live_metadata(rt, live=True)

    with rt.state_lock:
        rt.shadow_outputs.clear()

    rt.control_enabled = True
    rt.shadow_enabled = False
    rt.live_requested = True
    rt.arming = False
    rt.loop_mode = "live"

    print(f"🟢 [{rt.tent_id}] LIVE Hardware-Control freigegeben")
    return {
        "success": True,
        "tent_id": rt.tent_id,
        "mode": "live",
        "preflight": preflight,
    }


def request_live(tent_id):
    """Explicitly promotes a running shadow station when preflight is green."""

    tent_id = validate_tent_id(tent_id)
    rt = get_runtime(tent_id)

    if tent_id == DEFAULT_TENT_ID:
        return {
            "success": True,
            "tent_id": tent_id,
            "mode": "live",
            "already_live": True,
            "preflight": evaluate_live_preflight(rt),
        }

    with _transition_lock:
        if rt.control_enabled:
            return {
                "success": True,
                "tent_id": tent_id,
                "mode": "live",
                "already_live": True,
                "preflight": evaluate_live_preflight(rt),
            }

        if not rt.shadow_enabled:
            preflight = evaluate_live_preflight(rt)
            raise LiveTransitionError(
                "Station muss vor der LIVE-Freigabe als Shadow-Regelkreis laufen",
                preflight=preflight,
                code="shadow_required",
            )

        # The user-requested transition is only persisted after all checks pass.
        rt.arming = True
        try:
            result = _activate_runtime(rt, persist=True)
        except Exception:
            rt.arming = False
            rt.live_requested = False
            raise

        return result


def _safe_stop_assigned_relays(runtime):
    """Turns every assigned relay OFF and verifies it before closing the gate."""

    rt = resolve_runtime(runtime)
    failures = []

    for device, meta in DEVICE_HARDWARE.items():
        host = str(rt.config.get(meta["ip_key"]) or "").strip()
        relay = rt.config.get(meta["relay_key"])
        if not host or relay in (None, ""):
            continue

        try:
            relay = int(relay)
        except (TypeError, ValueError):
            failures.append(f"{meta['label']}: ungültiges Relay")
            continue

        health = get_endpoint_health(host, relay)
        actual = health.get("actual_state") if health else None

        # If the cache already knows it is OFF, no write is necessary.
        if actual is False and health.get("state") == "ok":
            _set_runtime_device_state(rt, device, False)
            continue

        if not switch_shelly(host, relay, False, timeout=2):
            failures.append(f"{meta['label']}: Ausschalten fehlgeschlagen")
            continue

        verify = get_shelly_relay_state(host, relay, timeout=2)
        if verify is not False:
            failures.append(f"{meta['label']}: AUS konnte nicht verifiziert werden")
            continue

        _set_runtime_device_state(rt, device, False)

    if failures:
        raise LiveTransitionError(
            "LIVE kann nicht verlassen werden, weil nicht alle Relais sicher AUS sind",
            code="safe_stop_failed",
            preflight={"ready": False, "blockers": failures},
        )


def request_shadow(tent_id):
    """Demotes LIVE -> SHADOW only after all assigned relays are safely OFF."""

    tent_id = validate_tent_id(tent_id)
    if tent_id == DEFAULT_TENT_ID:
        raise LiveTransitionError(
            "Die Default-Station bleibt LIVE",
            code="default_live_locked",
        )

    rt = get_runtime(tent_id)

    with _transition_lock:
        if rt.control_enabled:
            # Freeze normal controller/failsafe writes while the transition
            # service owns the relays. If safe-stop fails we can safely resume
            # LIVE afterwards without having raced the 2s controller loop.
            rt.disarming = True
            try:
                _safe_stop_assigned_relays(rt)
            except Exception:
                rt.disarming = False
                raise

            try:
                # Persist SHADOW only after the physical safe-stop succeeded.
                # If persistence fails, LIVE remains the authoritative target;
                # the controller may resume from the now-safe OFF relay state.
                _persist_live_metadata(rt, live=False)
            except Exception:
                rt.disarming = False
                raise

        else:
            _persist_live_metadata(rt, live=False)

        rt.control_enabled = False
        rt.live_requested = False
        rt.arming = False
        rt.shadow_enabled = True
        rt.loop_mode = "shadow"
        rt.disarming = False

        print(f"🟣 [{rt.tent_id}] LIVE beendet; Shadow-Regelkreis aktiv")
        return {
            "success": True,
            "tent_id": rt.tent_id,
            "mode": "shadow",
        }


def arm_requested_runtimes_once():
    """Attempts boot-time arming for stations persisted as LIVE."""

    results = []
    for rt in list_runtimes():
        if rt.tent_id == DEFAULT_TENT_ID:
            continue

        # Serialize automatic boot arming with explicit LIVE/SHADOW requests.
        # Without this lock an operator could request SHADOW at exactly the
        # moment the background arming loop opens the hardware gate.
        with _transition_lock:
            if not rt.enabled or not getattr(rt, "live_requested", False):
                continue
            if rt.control_enabled or getattr(rt, "disarming", False):
                continue

            rt.arming = True
            try:
                result = _activate_runtime(rt, persist=False)
                results.append(result)
            except LiveTransitionError as exc:
                rt.last_live_preflight = exc.preflight
                results.append({
                    "success": False,
                    "tent_id": rt.tent_id,
                    "mode": "arming",
                    "preflight": exc.preflight,
                })

    return results


def live_arming_loop():
    """Retries persisted LIVE stations after boot until their preflight is green."""

    print("🟠 Multi-Station LIVE-Arming Thread gestartet")
    last_blockers = {}

    while True:
        try:
            results = arm_requested_runtimes_once()
            for result in results:
                if result.get("success"):
                    last_blockers.pop(result["tent_id"], None)
                    continue

                tent_id = result["tent_id"]
                blockers = tuple((result.get("preflight") or {}).get("blockers") or [])
                if blockers != last_blockers.get(tent_id):
                    last_blockers[tent_id] = blockers
                    print(
                        f"🟠 [{tent_id}] ARMING wartet: "
                        + ("; ".join(blockers) if blockers else "Preflight nicht bereit")
                    )
        except Exception as exc:
            print("⚠️ LIVE-Arming Fehler:", exc)

        time.sleep(ARMING_RETRY_SEC)
