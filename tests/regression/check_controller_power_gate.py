#!/usr/bin/env python3
"""Regression for CTRL.3.3 runtime-config Shelly power gate."""

from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.controller_states import (
    _shelly_power_confirmed,
    apply_device_state,
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
        self.tent_id = "tent_1"
        self.config = {
            "IP_VENT": "192.0.2.10",
            "RELAY_VENT": 0,
        }
        self.state = DummyState()
        self.state_lock = DummyLock()
        self.control_enabled = True
        self.shadow_enabled = False


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)



def main():
    rt = DummyRuntime()
    rt.state.vent_on = True

    with patch(
        "core.controller_states.device_assignment",
        side_effect=AssertionError("Health-Fallback darf bei Runtime-EIN nicht nötig sein"),
    ):
        require(
            _shelly_power_confirmed(rt, "vent") is True,
            "Runtime-EIN bestätigt den Shelly-Powerzustand direkt",
        )

    rt = DummyRuntime()
    with (
        patch(
            "core.controller_states.get_endpoint_health",
            return_value={
                "state": "ok",
                "actual_state": True,
                "stale": False,
            },
        ),
    ):
        require(
            _shelly_power_confirmed(rt, "vent") is True,
            "Runtime-config + verifiziertes physisches Shelly-EIN geben Controllerwrite frei",
        )

    for health in (
        {"state": "ok", "actual_state": False},
        {"state": "warn", "actual_state": True},
        {"state": "error", "actual_state": None},
        None,
    ):
        rt = DummyRuntime()
        with (
            patch(
                "core.controller_states.get_endpoint_health",
                return_value=health,
            ),
        ):
            require(
                _shelly_power_confirmed(rt, "vent") is False,
                f"Unsicherer/AUS Shelly-Health blockiert Controllerwrite: {health!r}",
            )

    rt = DummyRuntime()
    rt.config["RELAY_VENT"] = "0"
    with patch(
        "core.controller_states.get_endpoint_health",
        return_value={"state": "ok", "actual_state": True},
    ) as health:
        require(
            _shelly_power_confirmed(rt, "vent") is True,
            "String-Relay aus runtime.config wird sicher normalisiert",
        )
        health.assert_called_once_with("192.0.2.10", 0)

    # End-to-end through apply_device_state:
    # set_device(True) leaves the cold runtime bit untouched, but the verified
    # physical relay state is ON, so the controller may be written.
    rt = DummyRuntime()
    applied = []

    with (
        patch("core.controller_states.resolve_runtime", return_value=rt),
        patch("core.controller_states.set_device") as shelly,
        patch(
            "core.controller_states.get_endpoint_health",
            return_value={"state": "ok", "actual_state": True},
        ),
        patch(
            "core.controller_states._apply_controller",
            side_effect=lambda runtime, device, values: (
                applied.append((device, values))
                or {"success": True, "status": "sent"}
            ),
        ),
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
        shelly.call_count == 1
        and applied == [("vent", {"level": 7})]
        and result["controller"]["status"] == "sent",
        "Physisch bestätigtes Shelly-EIN gibt den Modus-Level trotz kaltem Runtime-Bit frei",
    )

    # Hard invariant: power=False skips all controller logic, even if hardware
    # health would report ON.
    rt = DummyRuntime()
    with (
        patch("core.controller_states.resolve_runtime", return_value=rt),
        patch("core.controller_states.set_device") as shelly,
        patch("core.controller_states._apply_controller") as controller,
        patch("core.controller_states.get_endpoint_health") as health,
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
        shelly.call_count == 1
        and controller.call_count == 0
        and health.call_count == 0
        and result["controller"]["status"] == "skipped_power_off",
        "Power AUS bleibt hart Shelly-autoritativ und prüft/sendet keinen Controller",
    )

    print("✅ CTRL.3.3 Runtime-Power-Gate vollständig erfolgreich")


if __name__ == "__main__":
    main()
