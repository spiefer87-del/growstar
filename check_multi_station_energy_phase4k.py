#!/usr/bin/env python3
"""Growstar Phase 4K – Multi-Station Energy regression.

The dynamic service checks run entirely against in-memory fake runtimes and
fake HTTP responses. No Shelly request, relay write, config file write or live
Growstar runtime is touched.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import threading
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def static_checks():
    service = read("services/energy.py")
    routes = read("routes/energy.py")
    thread = read("threads/shelly.py")
    policy = read("auth/policy.py")
    page = read("templates/energie.html")
    settings = read("templates/energie_settings.html")
    test_src = read("check_multi_station_energy_phase4k.py")

    for name, source in (
        ("services/energy.py", service),
        ("routes/energy.py", routes),
        ("threads/shelly.py", thread),
        ("auth/policy.py", policy),
        ("check_multi_station_energy_phase4k.py", test_src),
    ):
        ast.parse(source, filename=name)
    print("✅ Python-Syntax Phase 4K")

    try:
        from jinja2 import Environment
        Environment().parse(page)
        Environment().parse(settings)
        print("✅ Jinja-Syntax Energie-Seiten")
    except ModuleNotFoundError:
        print("ℹ️ Jinja2 nicht installiert – Template-Parser übersprungen")

    require("ENERGY_DEVICES" not in service,
            "Energie-Poll ist nicht mehr an Legacy ENERGY_DEVICES gebunden")
    require("DEVICE_HARDWARE" in service and "list_runtimes" in service,
            "Energie-Poll folgt generischen Hardware-Zuordnungen aller Runtimes")
    require("plan.setdefault(endpoint" in service and "polled_endpoints" in service,
            "Physische Host/Relay-Endpunkte werden controllerweit dedupliziert")
    require("rt.energy_state" in service and "rt.energy_lock" in service,
            "Messwerte werden pro Runtime isoliert gespeichert")
    require("rt.config.setdefault(\"ENERGY_RESET\"" in service
            and "rt.config.setdefault(\"ENERGY_DAY_OFFSET\"" in service,
            "Reset-Offsets sind stationsbezogen")
    require("get_default_runtime" in service and "POWER_PRICE" in service,
            "Strompreis und Reset-Zeit bleiben bewusst controllerweite Einstellungen")
    require('/api/energy/overview' in routes,
            "Controllerweite Multi-Station-Energie-API vorhanden")
    require('/api/tents/<tent_id>/energy' in routes,
            "Stationsbezogene Energie-API vorhanden")
    require('return jsonify(get_runtime_energy_snapshot(get_default_runtime()))' in routes,
            "Legacy /api/energy bleibt Alias auf Default-Station")
    require('/api/energy/settings' in routes,
            "Eigener Energie-Einstellungsendpunkt ersetzt globales /api/config in UI")
    require('/api/energy/overview' in page and '/api/config' not in page,
            "Energie-Seite liest neue Multi-Station-API")
    require('Grow-Stationen' in page and 'Anteil am heutigen Gesamtverbrauch' in page,
            "Energie-Seite rendert Stationen und aktuelle Statistik dynamisch")
    require('/api/energy/settings' in settings and '/api/config' not in settings,
            "Energie-Einstellungen benutzen dedizierte Settings-API")
    require('/api/tents/${encodeURIComponent(tentId)}/energy/' in settings,
            "Reset pro Station/Gerät ist in der UI stationsbezogen")
    require("refresh_energy_state()" in thread and "legacy/default-station" not in thread,
            "Shelly-Thread pollt das neue Multi-Station-Energiesystem")
    require('if "/energy/reset_" in path:' in policy,
            "Stationsbezogene Energie-Resets sind explizit berechtigt")


def load_policy():
    spec = importlib.util.spec_from_file_location(
        "phase4k_policy",
        ROOT / "auth" / "policy.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def policy_checks():
    policy = load_policy()

    req = policy.permission_requirement("/api/energy/overview", "GET")
    require(req.allows({"grow.view"}) and not req.allows(set()),
            "Energie-Übersicht benötigt Grow-Leserecht")

    req = policy.permission_requirement("/api/energy/settings", "POST")
    require(req.allows({"settings.manage"}) and not req.allows({"grow.control"}),
            "Controllerweite Energie-Einstellungen benötigen settings.manage")

    req = policy.permission_requirement(
        "/api/tents/tent_2/energy/reset_today/heating",
        "POST",
    )
    require(req.allows({"grow.configure"}) and not req.allows({"grow.control"}),
            "Stationsbezogener Energie-Reset benötigt grow.configure")


class FakeRuntime:
    def __init__(self, tent_id, name, config, *, control=True):
        self.tent_id = tent_id
        self.name = name
        self.config = dict(config)
        self.energy_state = {}
        self.energy_lock = threading.RLock()
        self.enabled = True
        self.control_enabled = control
        self.arming = False
        self.shadow_enabled = not control
        self.loop_mode = "live" if control else "shadow"
        self.persist_count = 0

    def persist_config(self):
        self.persist_count += 1
        return True


class FakeResponse:
    def __init__(self, power, total_wh):
        self.status_code = 200
        self._payload = {
            "apower": power,
            "aenergy": {"total": total_wh},
        }

    def json(self):
        return self._payload


def load_service_with_stubs():
    saved = {
        name: sys.modules.get(name)
        for name in (
            "core",
            "core.context",
            "core.hardware_assignments",
            "core.runtime",
        )
    }

    core_pkg = types.ModuleType("core")
    core_pkg.__path__ = []
    sys.modules["core"] = core_pkg

    ctx = types.ModuleType("core.context")
    ctx.last_energy_poll = 1234.0
    sys.modules["core.context"] = ctx
    core_pkg.context = ctx

    assignments = types.ModuleType("core.hardware_assignments")
    assignments.DEVICE_HARDWARE = {
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
    sys.modules["core.hardware_assignments"] = assignments
    core_pkg.hardware_assignments = assignments

    runtime_module = types.ModuleType("core.runtime")
    runtime_module._runtimes = []

    def resolve_runtime(runtime=None):
        if runtime is None:
            return runtime_module._runtimes[0]
        if isinstance(runtime, str):
            for rt in runtime_module._runtimes:
                if rt.tent_id == runtime:
                    return rt
            raise KeyError(runtime)
        return runtime

    runtime_module.resolve_runtime = resolve_runtime
    runtime_module.list_runtimes = lambda: list(runtime_module._runtimes)
    runtime_module.get_default_runtime = lambda: runtime_module._runtimes[0]
    sys.modules["core.runtime"] = runtime_module
    core_pkg.runtime = runtime_module

    spec = importlib.util.spec_from_file_location(
        "phase4k_energy_service",
        ROOT / "services" / "energy.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module, runtime_module, saved


def restore_modules(saved):
    for name, original in saved.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


def dynamic_service_checks():
    service, runtime_module, saved = load_service_with_stubs()
    try:
        rt1 = FakeRuntime(
            "tent_1",
            "Zelt 1",
            {
                "IP_HEATING": "10.0.0.1",
                "RELAY_HEATING": 0,
                "IP_LIGHT": "10.0.0.9",
                "RELAY_LIGHT": 0,
                "POWER_PRICE": 0.50,
                "ENERGY_DAY_RESET_MIN": 60,
                "ENERGY_RESET": {},
                "ENERGY_DAY_OFFSET": {},
            },
        )
        rt2 = FakeRuntime(
            "tent_2",
            "Zelt 2",
            {
                "IP_HEATING": "10.0.0.2",
                "RELAY_HEATING": 0,
                # Deliberately duplicate this read-only test endpoint to prove
                # poll deduplication. Production assignment validation normally
                # prevents this situation.
                "IP_LIGHT": "10.0.0.9",
                "RELAY_LIGHT": 0,
                "ENERGY_RESET": {},
                "ENERGY_DAY_OFFSET": {},
            },
        )
        runtime_module._runtimes[:] = [rt1, rt2]

        raw = {
            ("10.0.0.1", 0): [100.0, 1000.0],
            ("10.0.0.2", 0): [200.0, 2000.0],
            ("10.0.0.9", 0): [50.0, 3000.0],
        }
        calls = []

        def fake_get(url, timeout):
            calls.append(url)
            host = url.split("http://", 1)[1].split("/", 1)[0]
            relay = int(url.rsplit("=", 1)[1])
            power, total_wh = raw[(host, relay)]
            return FakeResponse(power, total_wh)

        service.requests.get = fake_get

        result = service.refresh_energy_state()
        require(result["stations"] == 2,
                "Ein Poll-Zyklus verarbeitet beide Stationen")
        require(result["configured_devices"] == 4,
                "Alle konfigurierten Energie-Geräte werden Stationen zugeordnet")
        require(result["polled_endpoints"] == 3 and len(calls) == 3,
                "Doppelter physischer Endpoint wird nur einmal gepollt")
        require(set(rt1.energy_state) == {"heating", "light"}
                and set(rt2.energy_state) == {"heating", "light"},
                "Beide Runtimes besitzen getrennte Energie-States")
        require(rt1.energy_state is not rt2.energy_state,
                "Runtime-Energieobjekte sind nicht geteilt")

        # First daily reading creates the daily baseline, so today starts at 0.
        require(rt1.energy_state["heating"]["today"] == 0.0
                and rt2.energy_state["heating"]["today"] == 0.0,
                "Tagesoffset wird pro Station initialisiert")

        # Increase raw counters and poll again.
        raw[("10.0.0.1", 0)] = [110.0, 1250.0]
        raw[("10.0.0.2", 0)] = [220.0, 2400.0]
        raw[("10.0.0.9", 0)] = [60.0, 3300.0]
        service.refresh_energy_state()

        require(rt1.energy_state["heating"]["today"] == 0.25,
                "Zelt 1 Tagesverbrauch folgt eigenem Offset")
        require(rt2.energy_state["heating"]["today"] == 0.4,
                "Zelt 2 Tagesverbrauch folgt eigenem Offset")

        rt1_today_before = rt1.energy_state["heating"]["today"]
        service.reset_runtime_today(rt2, device="heating", today="2099-01-01")
        require(rt2.energy_state["heating"]["today"] == 0.0,
                "Geräte-Reset setzt nur ausgewählte Station zurück")
        require(rt1.energy_state["heating"]["today"] == rt1_today_before,
                "Reset von Zelt 2 verändert Zelt 1 nicht")
        require("heating" in rt2.config["ENERGY_DAY_OFFSET"]
                and rt1.config["ENERGY_DAY_OFFSET"] is not rt2.config["ENERGY_DAY_OFFSET"],
                "Tagesreset-Persistenz bleibt stationsisoliert")

        overview = service.build_energy_overview()
        require(len(overview["stations"]) == 2,
                "Übersicht liefert beliebig viele Stationen")
        require(overview["settings"]["power_price"] == 0.5,
                "Controller-Strompreis kommt bewusst aus Default-Runtime")
        require(overview["totals"]["power"] == 450.0,
                "Controller-Statistik summiert beide Stationen")
        require(overview["statistics"]["top_power"]["tent_id"] == "tent_2",
                "Statistik kann größten aktuellen Verbraucher stationsübergreifend bestimmen")

        service.update_energy_settings({"power_price": 0.61, "day_reset_min": 120})
        require(rt1.config["POWER_PRICE"] == 0.61
                and rt1.config["ENERGY_DAY_RESET_MIN"] == 120,
                "Globale Energie-Einstellungen werden in Default-Config persistiert")
        require("POWER_PRICE" not in rt2.config,
                "Globale Strompreisänderung schreibt nicht in Zelt-2-Config")

        service.reset_total_all_runtimes()
        require(rt1.energy_state["heating"]["total"] == 0.0
                and rt2.energy_state["heating"]["total"] == 0.0,
                "Controllerweiter Gesamtreset umfasst beide Stationen")

    finally:
        restore_modules(saved)


def main():
    static_checks()
    policy_checks()
    dynamic_service_checks()
    print("✅ Phase 4K Multi-Station Energy & Statistik vollständig")


if __name__ == "__main__":
    main()
