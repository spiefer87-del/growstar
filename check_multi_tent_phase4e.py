#!/usr/bin/env python3

"""Growstar Multi-Tent Phase 4E – safe regression checks.

The pure health test uses isolated stub modules, so it never reads or changes the
productive config.json/tents.json and never sends network requests.
"""

from pathlib import Path
import importlib.util
import sys
import threading
import time
import types


ROOT = Path(__file__).resolve().parent


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def static_checks():
    health = (ROOT / "core/watchdog_health.py").read_text(encoding="utf-8")
    service = (ROOT / "services/watchdog.py").read_text(encoding="utf-8")
    route = (ROOT / "routes/watchdog.py").read_text(encoding="utf-8")
    template = (ROOT / "templates/watchdog.html").read_text(encoding="utf-8")
    dashboard = (ROOT / "routes/dashboard.py").read_text(encoding="utf-8")
    hub = (ROOT / "templates/grow_control_dashboard.html").read_text(encoding="utf-8")
    blu = (ROOT / "threads/blu.py").read_text(encoding="utf-8")
    policy = (ROOT / "auth/policy.py").read_text(encoding="utf-8")

    check("list_runtimes" in health, "Watchdog iteriert generisch über alle Runtimes")
    check("last_loop_ts" in health, "Regelkreis-Heartbeat wird pro Runtime ausgewertet")
    check("SENSOR_ASSIGNMENTS" in health, "Sensorzustand wird stationsbezogen ausgewertet")
    check("DEVICE_HARDWARE" in health, "Hardware-Zuordnung wird stationsbezogen zusammengefasst")
    check('"reachability_checked": False' in health, "Watchdog sendet keine versteckten Hardware-Pings")
    check("watchdog_cycle" in service, "Watchdog-Zyklus ist separat testbar")
    check("[{tent_id}]" in service, "Watchdog-Log kennzeichnet Stationswarnungen")
    check('"stations"' in health, "Status-Snapshot enthält beliebig viele Stationen")
    check('"temp"' in health and '"hum"' in health, "Legacy TEMP/HUM Felder bleiben kompatibel")
    check('/api/watchdog/status' in route, "Bestehende Watchdog-Status-API bleibt vorhanden")
    check('/api/watchdog/log/clear' in route, "Bestehende Watchdog-Log-API bleibt vorhanden")
    check('id="stations"' in template, "Watchdog-Seite rendert Stationsliste dynamisch")
    check('/api/watchdog/status' in template, "Watchdog-Seite liest zentrale Status-API")
    check('/grow-control/watchdog' in dashboard, "Watchdog besitzt kanonische Grow-Control-Route")
    check("grow_control_watchdog" in hub, "Grow-Control-Hub verlinkt kanonischen Watchdog")
    check('name="growstar-blu"' in blu, "BLU Worker ist für Thread-Health eindeutig benannt")
    check('"/grow-control/watchdog": require("hardware.view")' in policy, "Watchdog behält hardware.view Leserecht")


def _load_health_with_stubs():
    """Load core/watchdog_health.py without touching the real Growstar runtime."""

    saved = {name: sys.modules.get(name) for name in (
        "core.context",
        "core.constants",
        "core.devices",
        "core.hardware_assignments",
        "core.runtime",
        "core.tents",
    )}

    ctx = types.ModuleType("core.context")
    ctx.MQTT_LAST_MSG = 0
    ctx.WATCHDOG_LAST_LOOP = 0
    ctx.energy_state = {}
    ctx.energy_lock = threading.RLock()

    constants = types.ModuleType("core.constants")
    constants.SENSOR_TIMEOUT = 60

    devices = types.ModuleType("core.devices")
    devices.DEVICE_MODES = {"OFF", "ON", "TIME", "INTERVAL", "ENV"}

    hardware = types.ModuleType("core.hardware_assignments")
    hardware.DEVICE_HARDWARE = {
        "heating": {
            "label": "Heizung",
            "ip_key": "IP_HEATING",
            "relay_key": "RELAY_HEATING",
        },
        "light": {
            "label": "Licht",
            "ip_key": "IP_LIGHT",
            "relay_key": "RELAY_LIGHT",
        },
    }

    runtime_module = types.ModuleType("core.runtime")
    runtime_module._test_runtimes = []
    runtime_module.list_runtimes = lambda: list(runtime_module._test_runtimes)

    tents = types.ModuleType("core.tents")
    tents.DEFAULT_TENT_ID = "tent_1"
    tents.manager = object()

    sys.modules["core.context"] = ctx
    sys.modules["core.constants"] = constants
    sys.modules["core.devices"] = devices
    sys.modules["core.hardware_assignments"] = hardware
    sys.modules["core.runtime"] = runtime_module
    sys.modules["core.tents"] = tents

    try:
        spec = importlib.util.spec_from_file_location(
            "phase4e_health_under_test",
            ROOT / "core/watchdog_health.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, runtime_module, ctx
    finally:
        for name, original in saved.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


def pure_health_checks():
    health, runtime_module, ctx = _load_health_with_stubs()

    class State:
        def __init__(self):
            self.last_ds_time = 0
            self.last_dht_time = 0
            self.temp_stale = False
            self.hum_stale = False
            self.live_state = {"temp": None, "hum": None}

    class Runtime:
        def __init__(self, tent_id, name, *, control=False, shadow=True):
            self.tent_id = tent_id
            self.name = name
            self.enabled = True
            self.control_enabled = control
            self.shadow_enabled = shadow
            self.loop_mode = "live" if control else "shadow"
            self.last_loop_ts = None
            self.state = State()
            self.config = {
                "SENSOR_ASSIGNMENTS": {
                    "temperature": {"source_id": f"test:{tent_id}:temp", "field": "temperature", "label": "T"},
                    "humidity": {"source_id": f"test:{tent_id}:hum", "field": "humidity", "label": "H"},
                },
                "DEVICE_MODES": {"heating": "ENV", "light": "OFF"},
            }

    now = 1_000.0
    a = Runtime("tent_1", "Zelt 1", control=True, shadow=False)
    a.last_loop_ts = now - 2
    a.state.last_ds_time = now - 3
    a.state.last_dht_time = now - 4
    a.state.live_state.update(temp=22.4, hum=55.0)
    a.config.update(IP_HEATING="192.0.2.10", RELAY_HEATING=0)

    b = Runtime("tent_2", "Zelt 2", control=False, shadow=True)
    b.last_loop_ts = now - 30
    b.state.last_ds_time = now - 120
    b.state.last_dht_time = now - 2
    b.state.temp_stale = True
    b.state.live_state.update(temp=None, hum=54.0)

    runtime_module._test_runtimes[:] = [a, b]
    ctx.MQTT_LAST_MSG = now - 5

    ha = health.station_health(a, now=now)
    hb = health.station_health(b, now=now)
    snapshot = health.build_watchdog_snapshot(now=now)

    check(ha["loop"]["stale"] is False, "Frischer LIVE-Regelkreis wird als gesund erkannt")
    check(ha["temperature"]["stale"] is False, "Frischer Temperatursensor wird erkannt")
    check(ha["humidity"]["stale"] is False, "Frischer Feuchtesensor wird erkannt")
    check(ha["hardware"]["assigned"] == 1, "Hardwarezuordnung wird gezählt")
    check(ha["hardware"]["reachability_checked"] is False, "Health-Snapshot bleibt netzwerkfrei")
    check(hb["loop"]["stale"] is True, "Hängender Shadow-Regelkreis wird per Heartbeat erkannt")
    check(hb["temperature"]["stale"] is True, "Staler Sensor wird stationsbezogen erkannt")
    check(hb["sensor_failsafe"]["active"] is True, "Sensor-Failsafe wird stationsbezogen sichtbar")
    check(len(snapshot["stations"]) == 2, "Snapshot enthält alle Teststationen")
    check(snapshot["temp"]["stale"] is False, "Legacy TEMP spiegelt weiterhin Default-Station")
    check(snapshot["mqtt"]["stale"] is False, "Controller-MQTT-Freshness wird getrennt bewertet")


def main():
    static_checks()
    pure_health_checks()
    print("✅ Phase 4E Multi-Station-Watchdog vollständig")


if __name__ == "__main__":
    main()
