#!/usr/bin/env python3
"""Regression for CTRL.1 controller-aware operating states."""

from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.controller_states import (
    apply_device_state,
    resolve_control_state,
)


class DummyState:
    def __init__(self):
        self.live_state = {}
        self.vent_on = False


class DummyLock:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class DummyRuntime:
    def __init__(self):
        self.tent_id = "default"
        self.config = {}
        self.state = DummyState()
        self.state_lock = DummyLock()
        self.control_enabled = True
        self.shadow_enabled = False


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    params = {
        "controller": {"level": 7},
    }

    require(
        resolve_control_state(params, "on") == {
            "power": True,
            "controller": {"level": 7},
        },
        "Dauerbetrieb übernimmt den bestehenden Controller-Sollwert",
    )

    require(
        resolve_control_state(params, "interval_a") == {
            "power": True,
            "controller": {"level": 7},
        },
        "Bestehendes Intervall bleibt in Phase A EIN mit Standard-Level",
    )

    require(
        resolve_control_state(params, "interval_b") == {
            "power": False,
            "controller": {},
        },
        "Bestehendes Intervall bleibt rückwärtskompatibel in Phase B AUS",
    )

    configured = {
        "controller": {"level": 7},
        "control_states": {
            "interval_a": {
                "power": True,
                "controller": {"level": 7},
            },
            "interval_b": {
                "power": True,
                "controller": {"level": 3},
            },
        },
    }

    require(
        resolve_control_state(configured, "interval_a") == {
            "power": True,
            "controller": {"level": 7},
        }
        and resolve_control_state(configured, "interval_b") == {
            "power": True,
            "controller": {"level": 3},
        },
        "Intervall unterstützt getrennte Leistungszustände A=L7 und B=L3",
    )

    rt = DummyRuntime()
    sent = []

    def fake_set_device(device, enabled, **kwargs):
        sent.append(("shelly", device, bool(enabled)))
        setattr(rt.state, f"{device}_on", bool(enabled))

    with (
        patch("core.controller_states.resolve_runtime", return_value=rt),
        patch("core.controller_states.set_device", side_effect=fake_set_device),
        patch("core.controller_states._apply_controller") as controller,
    ):
        result = apply_device_state(
            "vent",
            {
                "power": False,
                "controller": {"level": 10},
            },
            runtime=rt,
        )

        require(
            sent == [("shelly", "vent", False)],
            "AUS fordert ausschließlich Shelly AUS an",
        )
        require(
            controller.call_count == 0
            and result["controller"]["status"] == "skipped_power_off",
            "AUS sendet niemals einen Controller-Level-Befehl",
        )

    rt = DummyRuntime()
    sent = []

    def blocked_power(device, enabled, **kwargs):
        sent.append(("shelly", device, bool(enabled)))
        # Safety/Shadow simulation: logical runtime output remains OFF.

    with (
        patch("core.controller_states.resolve_runtime", return_value=rt),
        patch("core.controller_states.set_device", side_effect=blocked_power),
        patch("core.controller_states._apply_controller") as controller,
    ):
        result = apply_device_state(
            "vent",
            {
                "power": True,
                "controller": {"level": 7},
            },
            runtime=rt,
        )

        require(
            controller.call_count == 0
            and result["controller"]["status"] == "blocked_by_power_path",
            "Controller kann eine blockierte Shelly-/Safety-Powerfreigabe nicht umgehen",
        )

    print("✅ CTRL.1 Shelly-Priorität und Regelzustände vollständig erfolgreich")


if __name__ == "__main__":
    main()
