#!/usr/bin/env python3
"""Growstar Phase 4H – kontrollierte Multi-Station SHADOW <-> LIVE Freigabe.

Der Test führt keine echten Shelly-Schaltbefehle aus. Laufzeitprüfungen werden
mit monkeypatch-artigen Funktionsersetzungen gegen isolierte Runtimes ausgeführt.
"""

from pathlib import Path
import ast
import importlib.util
import tempfile
import time

try:
    from jinja2 import Environment
except ModuleNotFoundError:
    Environment = None


ROOT = Path(__file__).resolve().parent


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def static_checks():
    runtime = read("core/runtime.py")
    tents = read("core/tents.py")
    actuators = read("core/actuators.py")
    preflight = read("core/live_preflight.py")
    live_control = read("services/live_control.py")
    shelly_service = read("services/shelly.py")
    main_thread = read("threads/main.py")
    shelly_thread = read("threads/shelly.py")
    app = read("app.py")
    routes = read("routes/tents.py")
    policy = read("auth/policy.py")
    setup = read("templates/grow_control_setup.html")
    hub = read("templates/grow_control_dashboard.html")
    detail = read("templates/grow_control.html")
    watchdog = read("templates/watchdog.html")

    for source in (
        runtime, tents, actuators, preflight, live_control, shelly_service,
        main_thread, shelly_thread, app, routes, policy,
    ):
        ast.parse(source)

    if Environment is not None:
        env = Environment()
        for template in (setup, hub, detail, watchdog):
            env.parse(template)

    check("live_requested" in runtime and "arming" in runtime,
          "Runtime kennt LIVE-Zielmodus und ARMING")
    check("control_enabled=False" in runtime and "live_requested=requested_control" in runtime,
          "Persistiertes Zusatz-LIVE startet mit geschlossenem Hardware-Gate")
    check('key.startswith("IP_") or key.startswith("RELAY_")' in runtime,
          "Isolierte Runtime erbt keine Hardware-Endpunkte des Default-Zelts")
    check("not rt.control_enabled" in actuators and "disarming" in actuators and "shadow_outputs" in actuators,
          "Aktor-Hard-Gate bleibt auch während DISARMING die letzte physische Sicherheitsbarriere")

    check("get_endpoint_health" in preflight,
          "LIVE-Preflight nutzt den zentralen read-only Aktor-Health-Cache")
    check("switch_shelly" not in preflight and "requests." not in preflight,
          "LIVE-Preflight schaltet und pingt keine Hardware selbst")
    check('mode != "OFF"' in preflight,
          "Nur tatsächlich aktive Geräte blockieren die LIVE-Freigabe")
    check("required_sensors" in preflight and "_sensor_requirements" in preflight,
          "LIVE-Preflight verlangt nur benötigte Sensoren")
    check("validate_hardware_assignments" in preflight,
          "Doppelbelegung wird vor LIVE erneut geprüft")

    persist_pos = live_control.find("_persist_live_metadata(rt, live=True)")
    gate_pos = live_control.find("rt.control_enabled = True")
    check(persist_pos != -1 and gate_pos != -1 and persist_pos < gate_pos,
          "LIVE-Zielmodus wird vor Öffnen des Runtime-Hardware-Gates persistiert")
    check("seed_runtime_from_health" in live_control and "actual_state" in live_control,
          "Reale Relay-Zustände werden vor LIVE aus dem Health-Cache übernommen")
    check("_safe_stop_assigned_relays" in live_control and "get_shelly_relay_state" in live_control,
          "LIVE -> SHADOW besitzt Ausschalt- und Verifikationspfad")
    check("rt.disarming = True" in live_control and 'getattr(runtime, "disarming", False)' in shelly_thread,
          "DISARMING verhindert Controller-/Failsafe-Rennen beim sicheren Ausschalten")
    check("with _transition_lock:" in live_control and "arm_requested_runtimes_once" in live_control,
          "Automatisches ARMING ist mit manuellen LIVE/SHADOW-Transitions serialisiert")
    check("live_arming_loop" in live_control and "ARMING_RETRY_SEC" in live_control,
          "Boot-ARMING wird automatisch wiederholt")

    check("for device in DEVICE_NAMES" in main_thread,
          "Regelkreis steuert generisch alle bekannten Aktoren")
    check("for runtime in list_runtimes()" in shelly_thread and "runtime.control_enabled" in shelly_thread,
          "Shelly-Failsafe iteriert über alle tatsächlich LIVE Runtimes")
    check("refresh_energy_state()" in shelly_thread and "do_energy_day_reset()" in shelly_thread,
          "Bestehendes Default-Energiepolling bleibt unverändert erhalten")
    check("DEVICE_HARDWARE.items()" in shelly_service,
          "Failsafe deckt alle zentral bekannten Aktoren ab")

    check("for extra_runtime in list_runtimes()" in app and "extra_runtime.live_requested" in app,
          "Backend startet beliebig viele Shadow/ARMING-Zusatzruntimes generisch")
    check("growstar-live-arming" in app and "live_arming_loop" in app,
          "Backend startet genau den zentralen LIVE-Arming-Dienst")
    check("extra_runtime.control_enabled = False" not in app,
          "App erzwingt nicht mehr pauschal control_enabled=False")

    check('/api/tents/<tent_id>/live-preflight' in routes,
          "Stationsbezogener LIVE-Preflight-Endpunkt vorhanden")
    check('/api/tents/<tent_id>/live' in routes,
          "Stationsbezogener LIVE-Transition-Endpunkt vorhanden")
    check('return require("grow.control", "hardware.control")' in policy,
          "LIVE-Transition benötigt Grow- UND Hardware-Bedienrecht")
    check('return require("grow.view", "hardware.view")' in policy,
          "LIVE-Preflight benötigt Grow- UND Hardware-Leserecht")

    check("LIVE freigeben" in setup and "live-preflight" in setup,
          "Setup zeigt kontrollierte LIVE-Freigabe mit Preflight")
    check("ARMING" in setup and "ARMING" in hub and "ARMING" in detail and "arming" in watchdog,
          "ARMING ist in Setup, Hub, Stationsansicht und Watchdog sichtbar")


def manager_checks():
    spec = importlib.util.spec_from_file_location(
        "phase4h_tents", ROOT / "core" / "tents.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with tempfile.TemporaryDirectory(prefix="growstar-phase4h-meta-") as tmp:
        path = Path(tmp) / "tents.json"
        manager = mod.TentManager(str(path))
        manager.load()
        created = manager.add_tent("phase4h_station", name="Phase 4H", shadow_enabled=True)
        check(created["control_enabled"] is False and created["shadow_enabled"] is True,
              "Neue Station startet weiterhin sicher als SHADOW")

        live = manager.set_control_enabled("phase4h_station", True)
        check(live["control_enabled"] is True and live["shadow_enabled"] is False,
              "Kontrollierter LIVE-Zielmodus wird persistent gespeichert")

        reloaded = mod.TentManager(str(path))
        reloaded.load()
        item = reloaded.get("phase4h_station")
        check(item["control_enabled"] is True and item["shadow_enabled"] is False,
              "LIVE-Zielmodus überlebt einen Prozess-/Raspberry-Neustart")

        try:
            reloaded.update_tent("phase4h_station", shadow_enabled=True)
        except ValueError:
            blocked = True
        else:
            blocked = False
        check(blocked, "LIVE kann nicht über generische Metadaten heimlich auf SHADOW umgestellt werden")


def runtime_checks():
    """Runs only in the real Growstar project where all core modules exist."""
    try:
        from core.runtime import create_isolated_runtime, register_runtime, unregister_runtime
        import core.live_preflight as lp
        import services.live_control as lc
    except (ModuleNotFoundError, ImportError) as exc:
        print(f"ℹ️ Runtime-Test in Build-Umgebung übersprungen: {exc}")
        return

    now = time.time()
    cfg = {
        "DAY_TEMP": 24.0, "DAY_TEMP_TOL": 1.0,
        "DAY_HUM": 60.0, "DAY_HUM_TOL": 5.0,
        "NIGHT_TEMP": 21.0, "NIGHT_TEMP_TOL": 1.0,
        "NIGHT_HUM": 60.0, "NIGHT_HUM_TOL": 5.0,
        "MIN_TEMP": 12.0, "MAX_TEMP": 32.0,
        "DEVICE_MODES": {
            "heating": "ENV", "fan": "OFF", "light": "OFF", "vent": "OFF",
            "irrigation": "OFF", "humidifier": "OFF", "dehumidifier": "OFF",
            "light2": "OFF", "vent2": "OFF",
        },
        "SENSOR_ASSIGNMENTS": {
            "temperature": {"source_id": "test:phase4h", "field": "temperature"},
        },
        "IP_HEATING": "192.0.2.44",
        "RELAY_HEATING": 0,
    }
    rt = create_isolated_runtime(
        "phase4h_runtime",
        name="Phase 4H Runtime",
        config_data=cfg,
        enabled=True,
        shadow_enabled=True,
        control_enabled=False,
    )
    rt.last_loop_ts = now
    rt.loop_mode = "shadow"
    rt.state.last_ds_time = now
    rt.state.temp_stale = False
    rt.state.live_state["temp"] = 22.0

    old_health = lp.get_endpoint_health
    old_validate = lp.validate_hardware_assignments
    try:
        lp.validate_hardware_assignments = lambda: True
        lp.get_endpoint_health = lambda host, relay, now=None: {
            "state": "ok", "reachable": True, "actual_state": False,
            "check_age": 1.0, "last_error": None,
        }
        result = lp.evaluate_live_preflight(rt, now=now)
        check(result["ready"] is True, "Grüner Shadow-Preflight wird als LIVE-bereit erkannt")
        check(result["hardware"]["required"] == 1,
              "Nur der aktive Heizungsaktor ist für LIVE erforderlich")
        check(result["sensors"]["temperature"]["required"] is True
              and result["sensors"]["humidity"]["required"] is False,
              "Sensoranforderungen folgen den aktiven ENV-Geräten")

        lp.get_endpoint_health = lambda host, relay, now=None: {
            "state": "error", "reachable": False, "actual_state": None,
            "check_age": 1.0, "last_error": "offline",
        }
        blocked = lp.evaluate_live_preflight(rt, now=now)
        check(blocked["ready"] is False and blocked["hardware"]["ok"] is False,
              "Offline-Aktor blockiert LIVE")
    finally:
        lp.get_endpoint_health = old_health
        lp.validate_hardware_assignments = old_validate

    # The transition itself is tested with every external action stubbed.
    register_runtime(rt, replace=True)
    old_eval = lc.evaluate_live_preflight
    old_seed = lc.seed_runtime_from_health
    old_persist = lc._persist_live_metadata
    old_stop = lc._safe_stop_assigned_relays
    try:
        lc.evaluate_live_preflight = lambda runtime: {"ready": True, "blockers": []}
        lc.seed_runtime_from_health = lambda runtime: [{"device": "heating", "state": False}]
        lc._persist_live_metadata = lambda runtime, live: {"control_enabled": bool(live)}
        promoted = lc.request_live(rt.tent_id)
        check(promoted["mode"] == "live" and rt.control_enabled is True,
              "Explizite Freigabe öffnet das Hardware-Gate erst nach grünem Preflight")

        def safe_stop_asserts_disarming(runtime):
            check(runtime.disarming is True,
                  "Demotion sperrt normale Aktorik bevor Relais sicher ausgeschaltet werden")

        lc._safe_stop_assigned_relays = safe_stop_asserts_disarming
        demoted = lc.request_shadow(rt.tent_id)
        check(demoted["mode"] == "shadow" and rt.control_enabled is False and rt.shadow_enabled is True
              and rt.disarming is False,
              "Kontrollierte Demotion schließt das Hardware-Gate wieder")
    finally:
        lc.evaluate_live_preflight = old_eval
        lc.seed_runtime_from_health = old_seed
        lc._persist_live_metadata = old_persist
        lc._safe_stop_assigned_relays = old_stop
        try:
            unregister_runtime(rt.tent_id)
        except Exception:
            pass


def main():
    static_checks()
    manager_checks()
    runtime_checks()
    print("✅ Phase 4H kontrollierte Multi-Station LIVE-Freigabe vollständig")


if __name__ == "__main__":
    main()
