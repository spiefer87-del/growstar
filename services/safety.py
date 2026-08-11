"""Unabhaengiger stationsbezogener Safety-Supervisor.

Der Supervisor laeuft im bereits unabhaengigen Shelly-Background-Thread und
bewertet alle lokalen LIVE-Runtimes. Er verwendet keinerlei eigene Health-
Pings. Fuer sichere AUS-Aktionen nutzt er den normalen Aktorpfad, waehrend
core.actuators gleichzeitig ein erneutes Einschalten blockiert.
"""

from __future__ import annotations

import time

from core.actuators import set_device
from core.runtime import list_runtimes, resolve_runtime
from core.safety import (
    clear_runtime_safety,
    emergency_runtime_safety,
    evaluate_runtime_safety,
    get_runtime_safety_snapshot,
    store_runtime_safety,
)


def _current_device_on(runtime, device):
    st = runtime.state
    attr_value = getattr(st, f"{device}_on", None)
    live_value = st.live_state.get(device)
    return attr_value is True or live_value is True


def _log_transition(runtime, previous, current):
    previous = previous or {}
    # Beim allerersten Supervisor-Zyklus existiert noch kein echter vorheriger
    # Safety-Heartbeat. Ein gesunder Erststart soll deshalb nicht als
    # vermeintliche Recovery geloggt werden.
    had_previous_check = previous.get("checked_ts") is not None
    old_active = bool(previous.get("active")) if had_previous_check else False
    new_active = bool(current.get("active"))
    old_blocked = tuple(previous.get("blocked_devices") or [])
    new_blocked = tuple(current.get("blocked_devices") or [])
    old_reason = previous.get("reason")
    new_reason = current.get("reason")

    if new_active and (
        not old_active
        or old_blocked != new_blocked
        or old_reason != new_reason
    ):
        print(
            f"🚨 [{runtime.tent_id}] SAFETY FAILSAFE: "
            f"{new_reason or ', '.join(new_blocked)}"
        )
    elif old_active and not new_active:
        print(f"✅ [{runtime.tent_id}] SAFETY wieder NORMAL")


def _enforce_snapshot(runtime, snapshot):
    for device, override in (snapshot.get("overrides") or {}).items():
        if not override.get("force_off"):
            continue

        # Bei einem laut zentralem Health-Cache nicht erreichbaren Endpunkt
        # vermeiden wir 2-Sekunden-Netzwerkspam. Der Override bleibt aktiv und
        # blockiert neue EIN-Befehle. Sobald Hardware wieder verifiziert ist,
        # wird bei weiterhin bestehendem Sensor-/Loop-Fehler sofort AUS gesendet.
        if not override.get("can_attempt_off"):
            continue

        if not _current_device_on(runtime, device):
            continue

        reason = override.get("reason") or "Safety-Failsafe"
        set_device(
            device,
            False,
            runtime=runtime,
            reason=f"(SAFETY: {reason})",
        )


def run_runtime_safety(runtime=None, *, now=None, enforce=True):
    """Bewertet genau eine Runtime und erzwingt benoetigte Safe-Offs."""

    rt = resolve_runtime(runtime)
    now = time.time() if now is None else float(now)

    if (
        not rt.enabled
        or not rt.control_enabled
        or getattr(rt, "disarming", False)
    ):
        return clear_runtime_safety(
            rt,
            reason="Runtime nicht LIVE" if not rt.control_enabled else "DISARMING",
            now=now,
        )

    previous = get_runtime_safety_snapshot(rt, now=now)
    snapshot = evaluate_runtime_safety(rt, now=now)

    # Override zuerst atomar setzen. Dadurch kann ein parallel laufender
    # Regelzyklus ab diesem Moment keinen blockierten EIN-Befehl mehr senden.
    store_runtime_safety(rt, snapshot)
    _log_transition(rt, previous, snapshot)

    if enforce:
        _enforce_snapshot(rt, snapshot)

    return snapshot


def run_all_live_safety(*, now=None, enforce=True):
    """Ein Supervisor-Zyklus ueber beliebig viele lokale Stationen."""

    now = time.time() if now is None else float(now)
    result = {}

    for runtime in list_runtimes():
        try:
            result[runtime.tent_id] = run_runtime_safety(
                runtime,
                now=now,
                enforce=enforce,
            )
        except Exception as exc:
            # Ein Fehler einer Station darf die Safety-Bewertung der anderen
            # Stationen niemals abbrechen. Die betroffene LIVE-Runtime faellt
            # gleichzeitig fail-closed auf block_on/force_off fuer alle aktiven
            # Geraete, statt mit alten oder leeren Overrides weiterzulaufen.
            print(f"❌ [{runtime.tent_id}] Safety Supervisor Fehler: {exc}")
            emergency = emergency_runtime_safety(
                runtime,
                reason=str(exc),
                now=now,
            )
            store_runtime_safety(runtime, emergency)
            if enforce:
                _enforce_snapshot(runtime, emergency)
            result[runtime.tent_id] = emergency

    return result
