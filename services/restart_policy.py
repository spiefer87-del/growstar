"""Physische Umsetzung der Growstar-Neustart-Policy."""

from __future__ import annotations

from core.actuators import get_shelly_relay_state, switch_shelly
from core.hardware_assignments import DEVICE_HARDWARE, device_display_label
from core.restart_policy import (
    RESTART_KEEP,
    RESTART_OFF,
    get_restart_action,
)
from core.runtime import resolve_runtime


def _set_runtime_device_state(runtime, device, value):
    value = bool(value)
    with runtime.state_lock:
        setattr(runtime.state, f"{device}_on", value)
        runtime.state.live_state[device] = value


def apply_shutdown_restart_policy(runtime=None, *, verify=True):
    """Wendet die konfigurierte Policy auf genau eine Station an.

    KEEP erzeugt ausdrücklich keinerlei Shelly-Schreibzugriff.
    OFF sendet unabhängig vom möglicherweise veralteten In-Memory-State einen
    realen AUS-Befehl und verifiziert ihn optional direkt am Relay.
    """

    rt = resolve_runtime(runtime)
    result = {
        "tent_id": rt.tent_id,
        "success": True,
        "devices": {},
        "failures": [],
    }

    for device, meta in DEVICE_HARDWARE.items():
        action = get_restart_action(device, runtime=rt)
        label = device_display_label(rt.config, device)
        host = str(rt.config.get(meta["ip_key"]) or "").strip()
        relay = rt.config.get(meta["relay_key"])

        item = {
            "device": device,
            "label": label,
            "action": action,
            "configured": bool(host and relay not in (None, "")),
            "changed": False,
            "verified": None,
            "error": None,
        }

        result["devices"][device] = item

        if action == RESTART_KEEP:
            # Kern der neuen Funktion: kein physischer Schreibbefehl.
            continue

        if action != RESTART_OFF:
            item["error"] = f"Unbekannte Aktion {action}"
            result["failures"].append(f"{label}: {item['error']}")
            continue

        if not item["configured"]:
            continue

        try:
            relay = int(relay)
        except (TypeError, ValueError):
            item["error"] = "ungültiges Relay"
            result["failures"].append(f"{label}: {item['error']}")
            continue

        if not switch_shelly(host, relay, False, timeout=2):
            item["error"] = "Ausschalten fehlgeschlagen"
            result["failures"].append(f"{label}: {item['error']}")
            continue

        item["changed"] = True

        if verify:
            actual = get_shelly_relay_state(host, relay, timeout=2)
            item["verified"] = actual is False
            if actual is not False:
                item["error"] = "AUS konnte nicht verifiziert werden"
                result["failures"].append(f"{label}: {item['error']}")
                continue
        else:
            item["verified"] = None

        _set_runtime_device_state(rt, device, False)

    result["success"] = not result["failures"]
    return result
