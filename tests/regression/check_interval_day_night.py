#!/usr/bin/env python3
"""Regression für vollständige Tag-/Nacht-Profile im Intervallmodus."""

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
        "interval_night_on": 120,
        "interval_night_off": 180,
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

    independent_power = {
        "control_states": {
            "interval_b": {"power": False, "controller": {}},
            "interval_b_night": {
                "power": True,
                "controller": {"level": 10},
            },
        }
    }
    require(
        resolve_control_state(independent_power, "interval_b_night") == {
            "power": True,
            "controller": {"level": 10},
        },
        "Nachtphasen besitzen einen vom Tag unabhängigen Shelly-Zustand",
    )

    independent_power["control_states"]["interval_b"] = {
        "power": True,
        "controller": {"level": 4},
    }
    independent_power["control_states"]["interval_b_night"] = {
        "power": False,
        "controller": {"level": 10},
    }
    require(
        resolve_control_state(independent_power, "interval_b_night") == {
            "power": False,
            "controller": {},
        },
        "Eine Nachtphase kann unabhängig vom Tag vollständig ausgeschaltet werden",
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
            patch("core.control.get_profile", return_value=profile) as profile_lookup,
            patch(
                "core.control.apply_device_state",
                side_effect=lambda device, state, **kwargs: applied.append(state),
            ),
        ):
            control.control_device("vent", runtime=runtime)
        return profile_lookup.called

    run(timestamp=100, profile="TAG")
    run(timestamp=100, profile="NACHT")
    run(timestamp=200, profile="NACHT")
    profile_used_while_disabled = run(
        timestamp=100,
        profile="NACHT",
        enabled=False,
    )
    require(
        applied == [
            resolve_control_state(params, "interval_a"),
            resolve_control_state(params, "interval_a_night"),
            resolve_control_state(params, "interval_b_night"),
            resolve_control_state(params, "interval_a"),
        ],
        "Regelzyklus verwendet für die Nacht eigene Dauerwerte und Zustände",
    )
    require(
        profile_used_while_disabled is False,
        "Ohne Aktivierung läuft das Intervall vollständig profilunabhängig",
    )

    template = (ROOT / "templates/device_control.html").read_text(encoding="utf-8")
    for token in (
        'id="interval-night-enabled"',
        'id="interval-a-night-controller"',
        'id="interval-b-night-controller"',
        'id="interval-a-night-minutes"',
        'id="interval-b-night-minutes"',
        'id="interval-a-night-power"',
        'id="interval-b-night-power"',
        'id="tag-profile-window"',
        'id="night-profile-window"',
        "interval_night_enabled:",
        "interval_night_on:",
        "interval_night_off:",
        "interval_a_night:",
        "interval_b_night:",
    ):
        require(token in template, f"Intervall-UI enthält {token}")

    require(
        'class="interval-day-options"' in template
        and 'classList.toggle("profile-aware", profileAware)' in template
        and "Profilzeiten dieser Station" in template,
        "Aktivierung hebt Tag und Nacht samt Zeitfenstern farblich hervor",
    )

    route_source = (ROOT / "routes/device.py").read_text(encoding="utf-8")
    require(
        '"profile_schedule"' in route_source
        and '"day_start_min"' in route_source
        and '"night_start_min"' in route_source,
        "Geräte-API liefert die stationsbezogenen Profilzeiten",
    )

    print("✅ INTERVAL.NIGHT.2 vollständig erfolgreich")


if __name__ == "__main__":
    main()
