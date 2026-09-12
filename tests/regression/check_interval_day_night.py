#!/usr/bin/env python3
"""Regression für getrennte Controllerwerte im Tag-/Nacht-Intervall."""

from pathlib import Path
import sys
import types
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")
    requests_stub.Timeout = type("Timeout", (Exception,), {})
    requests_stub.ConnectionError = type("ConnectionError", (Exception,), {})
    requests_stub.RequestException = type("RequestException", (Exception,), {})
    requests_stub.get = lambda *args, **kwargs: None
    requests_stub.post = lambda *args, **kwargs: None
    sys.modules["requests"] = requests_stub

from core import control
from core.controller_states import resolve_control_state


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    params = {
        "interval_on": 300,
        "interval_off": 900,
        "interval_night_enabled": True,
        "control_states": {
            "interval_a": {
                "power": True,
                "controller": {"level": 7, "oscillation": 6},
            },
            "interval_b": {
                "power": True,
                "controller": {"level": 4, "oscillation": 4},
            },
            "interval_a_night": {
                "power": True,
                "controller": {"level": 3, "oscillation": 2},
            },
            "interval_b_night": {
                "power": True,
                "controller": {"level": 2, "oscillation": 1},
            },
        },
    }

    require(
        resolve_control_state(params, "interval_a_night") == {
            "power": True,
            "controller": {"level": 3, "oscillation": 2},
        }
        and resolve_control_state(params, "interval_b_night") == {
            "power": True,
            "controller": {"level": 2, "oscillation": 1},
        },
        "Phase A und B besitzen im Nachtprofil eigene Controllerwerte",
    )

    legacy = {
        "control_states": {
            "interval_a": {"power": True, "controller": {"level": 7}},
            "interval_b": {"power": True, "controller": {"level": 4}},
        }
    }
    require(
        resolve_control_state(legacy, "interval_a_night")
        == resolve_control_state(legacy, "interval_a")
        and resolve_control_state(legacy, "interval_b_night")
        == resolve_control_state(legacy, "interval_b"),
        "Bestehende Konfigurationen fallen nachts sicher auf ihre Tagwerte zurück",
    )

    power_off = {
        "control_states": {
            "interval_b": {"power": False, "controller": {}},
            "interval_b_night": {
                "power": True,
                "controller": {"level": 10},
            },
        }
    }
    require(
        resolve_control_state(power_off, "interval_b_night") == {
            "power": False,
            "controller": {},
        },
        "Shelly-Power der Grundphase bleibt auch nachts autoritativ",
    )

    runtime = object()
    applied = []

    def run(*, timestamp, profile, enabled=True):
        params["interval_night_enabled"] = enabled
        with (
            patch("core.control.resolve_runtime", return_value=runtime),
            patch("core.control.get_device_mode", return_value="INTERVAL"),
            patch("core.control.get_device_params", return_value=params),
            patch("core.control.time.time", return_value=timestamp),
            patch("core.control.get_profile", return_value=profile),
            patch(
                "core.control.apply_device_state",
                side_effect=lambda device, state, **kwargs: applied.append(state),
            ),
        ):
            control.control_device("vent", runtime=runtime)

    run(timestamp=100, profile="TAG")
    run(timestamp=100, profile="NACHT")
    run(timestamp=400, profile="NACHT")
    run(timestamp=100, profile="NACHT", enabled=False)
    require(
        applied == [
            resolve_control_state(params, "interval_a"),
            resolve_control_state(params, "interval_a_night"),
            resolve_control_state(params, "interval_b_night"),
            resolve_control_state(params, "interval_a"),
        ],
        "Regelzyklus wählt automatisch Tag A, Nacht A oder Nacht B",
    )

    template = (ROOT / "templates/device_control.html").read_text(encoding="utf-8")
    for token in (
        'id="interval-night-enabled"',
        'id="interval-a-night-controller"',
        'id="interval-b-night-controller"',
        "interval_night_enabled:",
        "interval_a_night:",
        "interval_b_night:",
    ):
        require(token in template, f"Intervall-UI enthält {token}")

    require(
        "Dauer und Shelly-Power bleiben unverändert" in template
        and "Tag-/Nacht-Zeiten dieser Station" in template,
        "UI erklärt automatische Umschaltung und unveränderte Powerphasen",
    )

    print("✅ INTERVAL.NIGHT.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
