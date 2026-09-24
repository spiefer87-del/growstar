#!/usr/bin/env python3
"""Daily Zeitschaltuhr boundaries, validation, persistence and station safety."""

from pathlib import Path
from unittest.mock import patch
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if "requests" not in sys.modules:
    requests = types.ModuleType("requests")
    requests.Timeout = type("Timeout", (Exception,), {})
    requests.ConnectionError = type("ConnectionError", (Exception,), {})
    requests.RequestException = type("RequestException", (Exception,), {})
    requests.get = requests.post = lambda *args, **kwargs: None
    sys.modules["requests"] = requests

from core import control
from core.controller_states import resolve_control_state
from core.devices import get_device_mode, get_device_params, update_device_config
from core.live_preflight import _config_check
from core.runtime import create_isolated_runtime
from core.timer_schedule import timer_is_on, validate_timer_windows
from core.watchdog_health import _config_health


def require(condition, message):
    assert condition, message
    print("✅", message)


def invalid(windows):
    try:
        validate_timer_windows(windows, require_one=True)
    except ValueError:
        return True
    return False


def main():
    windows = [
        {"start_min": 21 * 60, "end_min": 21 * 60 + 3},
        {"start_min": 2 * 60 + 5, "end_min": 2 * 60 + 8},
        {"start_min": 12 * 60, "end_min": 12 * 60 + 3},
    ]
    require([timer_is_on(windows, m) for m in (1259, 1260, 1262, 1263,
            124, 125, 127, 128, 720, 723)] ==
            [False, True, True, False, False, True, True, False, True, False],
            "Drei tägliche Pumpenfenster schalten an exakten Minutengrenzen")
    overnight = [{"start_min": 23 * 60 + 58, "end_min": 2}]
    require([timer_is_on(overnight, m) for m in (1437, 1438, 1439, 0, 1, 2)] ==
            [False, True, True, True, True, False],
            "Fenster über Mitternacht endet genau zur angegebenen Zeit")
    require(invalid(overnight + [{"start_min": 0, "end_min": 1}])
            and invalid([{"start_min": 60, "end_min": 80}, {"start_min": 70, "end_min": 90}])
            and invalid([{"start_min": 40, "end_min": 40}])
            and invalid([{"start_min": -1, "end_min": 4}])
            and invalid([{"start_min": "60", "end_min": 70}])
            and invalid([]), "Überlappung, leere und ungültige Fenster werden abgewiesen")
    require(not timer_is_on(None, 60) and not timer_is_on(windows, 1440),
            "Beschädigte oder leere Zeitpläne bleiben AUS")

    saved = []
    pump = create_isolated_runtime("tent_1", config_data={
        "IP_AUX1": "192.0.2.1", "RELAY_AUX1": 0,
        "DEVICE_MODES": {"aux1": "OFF"},
    }, save_config_callback=lambda cfg: saved.append(cfg.copy()), control_enabled=True)
    other = create_isolated_runtime("tent_2", config_data={
        "DEVICE_MODES": {"aux1": "OFF"},
    })
    # The existing assignment guard must stay active; fake only the resolved
    # hardware assignment so no network or physical relay is involved.
    with patch("core.hardware_assignments.device_assignment", return_value={"configured": True}):
        update_device_config("aux1", {"mode": "TIMER", "params": {"timer_windows": windows}}, runtime=pump)
        require(get_device_mode("aux1", runtime=pump) == "TIMER"
                and len(saved) == 1 and get_device_mode("aux1", runtime=other) == "OFF",
                "Modus und drei Fenster werden nur in Zelt 1 gespeichert")
        before = get_device_params("aux1", runtime=pump)["timer_windows"]
        try:
            update_device_config("aux1", {"mode": "TIMER", "params": {"timer_windows": []}}, runtime=pump)
            raise AssertionError("Leerer aktiver Zeitplan angenommen")
        except ValueError:
            pass
        require(get_device_params("aux1", runtime=pump)["timer_windows"] == before and len(saved) == 1,
                "Ungültiges Speichern lässt den letzten gültigen Plan bestehen")

    applied = []
    with patch("core.control.minutes_now", side_effect=[1260, 1263, 125, 128]), patch(
        "core.control.apply_device_state", side_effect=lambda device, state, runtime: applied.append((device, state))
    ):
        for _ in range(4):
            control.control_device("aux1", runtime=pump)
    require([state["power"] for _, state in applied] == [True, False, True, False],
            "EIN und AUS gehen durch denselben bestehenden Shelly-Schutzpfad")
    require(resolve_control_state({"control_states": {"timer": {"power": True, "controller": {"level": 6}}}}, "timer") ==
            {"power": True, "controller": {"level": 6}},
            "Zeitschaltuhr hat einen eigenen Controller-Zustand")
    pump.config["DEVICE_PARAMS"]["aux1"]["timer_windows"] = []
    require(not _config_check(pump, [("aux1", "TIMER")])["ok"],
            "LIVE-Preflight verweigert einen leeren Pumpenzeitplan")
    require(any("aux1: Zeitschaltuhr" in issue for issue in _config_health(pump)["issues"]),
            "Watchdog zeigt beschädigten Pumpenzeitplan an")
    print("✅ DAILY-TIMER.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
