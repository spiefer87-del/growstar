#!/usr/bin/env python3
"""Regression für Geräte-Sollwerte und bestätigte Aktorwechsel."""

import tempfile
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

if "flask" not in sys.modules:
    flask_stub = types.ModuleType("flask")
    flask_stub.jsonify = lambda *args, **kwargs: {"args": args, **kwargs}
    flask_stub.request = types.SimpleNamespace()
    sys.modules["flask"] = flask_stub

from core.actuators import set_heating
from core.runtime import create_isolated_runtime
from routes import device as device_routes
from services import grow_events


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    runtime = create_isolated_runtime(
        "tent_2",
        name="Zelt 2",
        config_data={
            "IP_HEATING": "192.0.2.10",
            "RELAY_HEATING": 0,
            "DEVICE_MODES": {"heating": "ENV", "light": "ENV"},
            "DEVICE_PARAMS": {
                "light": {
                    "control_states": {
                        "env": {
                            "power": True,
                            "controller": {"level": 80},
                        },
                    },
                },
            },
        },
        save_config_callback=lambda cfg: None,
        control_enabled=True,
        live_requested=True,
    )
    light_schema = {
        "level": {
            "label": "Lichtstärke",
            "unit": "%",
        },
    }

    original_db = grow_events.DB_FILE
    with tempfile.TemporaryDirectory(prefix="growstar-device-events-") as temp_dir:
        grow_events.DB_FILE = Path(temp_dir) / "events.db"
        try:
            grow_events.init_grow_event_db()

            before = device_routes._device_setting_snapshot(
                runtime,
                "light",
                schema=light_schema,
            )
            runtime.config["DEVICE_PARAMS"]["light"]["control_states"]["env"]["controller"]["level"] = 83
            after = device_routes._device_setting_snapshot(
                runtime,
                "light",
                schema=light_schema,
            )
            queued = device_routes._enqueue_device_setting_change(
                runtime,
                "light",
                before,
                after,
            )
            grow_events.flush_event_queue(limit=100)

            settings_events = grow_events.list_events(
                station_id="tent_2",
                category="device",
                since=0,
            )["items"]
            setting = next(
                item for item in settings_events
                if item["event_type"] == "device_settings_updated"
            )
            require(
                queued is True
                and "ENV · Lichtstärke: 80 % → 83 %" in setting["summary"]
                and setting["station_id"] == "tent_2",
                "Lichtdimmung wird mit Station und Vorher-/Nachher-Wert erfasst",
            )

            with patch("core.actuators.switch_shelly", return_value=True) as shelly:
                set_heating(True, "(unter Soll 25,0 °C)", runtime=runtime)
                set_heating(True, "(unter Soll 25,0 °C)", runtime=runtime)

            grow_events.flush_event_queue(limit=100)
            actuator_events = [
                item for item in grow_events.list_events(
                    station_id="tent_2",
                    category="device",
                    since=0,
                )["items"]
                if item["event_type"] == "actuator_power_changed"
            ]
            require(
                shelly.call_count == 1
                and len(actuator_events) == 1
                and actuator_events[0]["title"] == "Heizung eingeschaltet"
                and actuator_events[0]["metadata"]["modus"] == "ENV"
                and "unter Soll 25,0 °C" in actuator_events[0]["summary"],
                "Nur der bestätigte Heizung-Zustandswechsel wird einmal protokolliert",
            )
        finally:
            grow_events.DB_FILE = original_db

    print("✅ INTELLIGENCE.DEVICES.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
