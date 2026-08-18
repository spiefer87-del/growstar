"""Konfigurierbares Verhalten physischer Aktoren bei Growstar-Neustarts.

Die Policy gilt für geordnete Prozess-/systemd-Shutdowns. Bei einem abrupten
Stromausfall kann Growstar naturgemäß keinen letzten Shelly-Befehl mehr senden.
"""

from __future__ import annotations

from copy import deepcopy

from core.devices import (
    DEVICE_NAMES,
    get_device_icon,
    get_device_label,
    validate_device_name,
)
from core.runtime import resolve_runtime


RESTART_POLICY_KEY = "RESTART_POLICY"

RESTART_KEEP = "KEEP"
RESTART_OFF = "OFF"
RESTART_ACTIONS = {RESTART_KEEP, RESTART_OFF}

# Sichere Ausgangsbasis:
# - Beleuchtung bleibt bei einem kurzen Growstar-Neustart physisch unverändert.
# - Alle anderen Aktoren werden zunächst sicher AUS gefahren.
# Der Benutzer kann jeden Slot stationsbezogen im Setup umstellen.
DEFAULT_RESTART_POLICY = {
    device: RESTART_OFF
    for device in DEVICE_NAMES
}
DEFAULT_RESTART_POLICY["light"] = RESTART_KEEP
DEFAULT_RESTART_POLICY["light2"] = RESTART_KEEP


def normalize_restart_action(value):
    action = str(value or "").strip().upper()
    if action not in RESTART_ACTIONS:
        raise ValueError(
            "Ungültiges Neustart-Verhalten. Erlaubt sind KEEP und OFF."
        )
    return action


def get_restart_policy(runtime=None):
    """Liefert eine vollständige Policy ohne die Runtime beim Lesen zu verändern."""

    rt = resolve_runtime(runtime)
    configured = rt.config.get(RESTART_POLICY_KEY)
    if not isinstance(configured, dict):
        configured = {}

    policy = deepcopy(DEFAULT_RESTART_POLICY)

    for device, value in configured.items():
        if device not in DEVICE_NAMES:
            continue
        try:
            policy[device] = normalize_restart_action(value)
        except ValueError:
            # Manuell beschädigte Werte fallen fail-safe auf den Standard zurück.
            continue

    return policy


def get_restart_action(device, runtime=None):
    validate_device_name(device)
    return get_restart_policy(runtime).get(
        device,
        DEFAULT_RESTART_POLICY[device],
    )


def restart_policy_snapshot(runtime=None):
    rt = resolve_runtime(runtime)
    policy = get_restart_policy(rt)

    return {
        "success": True,
        "tent_id": rt.tent_id,
        "name": rt.name,
        "policy": policy,
        "devices": [
            {
                "device": device,
                "label": get_device_label(device, runtime=rt),
                "icon": get_device_icon(device),
                "action": policy[device],
                "default_action": DEFAULT_RESTART_POLICY[device],
            }
            for device in DEVICE_NAMES
        ],
        "actions": {
            RESTART_KEEP: "Zustand beibehalten",
            RESTART_OFF: "Sicher AUS",
        },
        "scope": "graceful_shutdown_restart",
    }


def update_restart_policy(values, runtime=None):
    """Speichert die stationsbezogene Neustart-Policy atomar."""

    if not isinstance(values, dict):
        raise TypeError("restart policy muss ein JSON-Objekt sein")

    unknown = sorted(set(values) - set(DEVICE_NAMES))
    if unknown:
        raise ValueError(
            "Unbekannte Aktoren in der Neustart-Policy: "
            + ", ".join(unknown)
        )

    rt = resolve_runtime(runtime)
    working = deepcopy(rt.config)
    current = working.get(RESTART_POLICY_KEY)

    if not isinstance(current, dict):
        current = {}

    for device, value in values.items():
        current[device] = normalize_restart_action(value)

    working[RESTART_POLICY_KEY] = current

    rt.config.clear()
    rt.config.update(working)
    rt.persist_config()

    return restart_policy_snapshot(rt)
