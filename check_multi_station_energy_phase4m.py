#!/usr/bin/env python3
"""Growstar Phase 4M – Energie-Historie, Tagespeaks und Diagramme.

Hardware-/Netzwerkfrei:
- services.energy wird mit Fake-Runtimes geladen;
- SQLite läuft in einer temporären Datei;
- es werden keine Shelly-Requests ausgeführt.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import sys
import tempfile
import threading
import types
from pathlib import Path

try:
    from jinja2 import Environment
except ModuleNotFoundError:
    Environment = None


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
    energy = read("templates/energie.html")
    grow = read("templates/grow_control.html")
    self_src = read("check_multi_station_energy_phase4m.py")

    for name, src in (
        ("services/energy.py", service),
        ("routes/energy.py", routes),
        ("threads/shelly.py", thread),
        ("check_multi_station_energy_phase4m.py", self_src),
    ):
        ast.parse(src, filename=name)
    print("✅ Python-Syntax Phase 4M")

    if Environment is not None:
        Environment().parse(energy)
        Environment().parse(grow)
        print("✅ Jinja-Syntax Phase 4M")

    require(
        "energy_history" in service
        and "energy_daily_peaks" in service,
        "Persistente Energie-Historie und Tagespeak-Tabelle vorhanden",
    )
    require(
        "ENERGY_HISTORY_SAMPLE_SEC = 120" in service
        and "ENERGY_HISTORY_RETENTION_DAYS = 90" in service,
        "Historie nutzt 2-Minuten-Samples und 90 Tage Aufbewahrung",
    )
    require(
        "record_energy_history()" in thread
        and "refresh_energy_state()" in thread,
        "Historie wird direkt nach dem bestehenden Energiepoll gespeichert",
    )
    require(
        "requests." not in service[service.index("def record_energy_history"):service.index("def _read_daily_peak_rows")],
        "History-Recorder erzeugt keine zusätzlichen Netzwerkrequests",
    )
    require(
        '/api/energy/history' in routes,
        "Read-only History-API vorhanden",
    )
    require(
        "Tagesmaximum" in energy
        and "Gesamtleistung im Verlauf" in energy
        and "Verbrauch heute nach Station" in energy
        and "Aktuelle Leistung nach Gerät" in energy,
        "Energie-Seite besitzt Tagesmaximum und mehrere Diagramme",
    )
    require(
        "Chart.js" not in energy
        and "<svg" in energy,
        "Diagramme benötigen keine externe Chart-Bibliothek",
    )
    require(
        "Hardware bestätigt" not in grow,
        "Normale Gerätekacheln zeigen keinen Hardware-Poll-Text mehr",
    )
    require(
        "device.physical_known" in grow
        and "device.physical_on" in grow,
        "Kachelfarbe folgt weiterhin dem verifizierten Hardwarezustand",
    )


class FakeRuntime:
    def __init__(self, tent_id, name, state):
        self.tent_id = tent_id
        self.name = name
        self.energy_state = state
        self.energy_lock = threading.RLock()
        self.enabled = True
        self.control_enabled = True
        self.arming = False
        self.shadow_enabled = False
        self.loop_mode = "live"
        self.config = {
            "POWER_PRICE": 0.5,
            "ENERGY_DAY_RESET_MIN": 0,
        }

    def persist_config(self):
        return True


def load_service(runtimes, db_path):
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
        "vent": {
            "label": "Ventilator",
            "ip_key": "IP_VENT",
            "relay_key": "RELAY_VENT",
        },
    }
    sys.modules["core.hardware_assignments"] = assignments
    core_pkg.hardware_assignments = assignments

    runtime_mod = types.ModuleType("core.runtime")
    runtime_mod.resolve_runtime = lambda rt=None: rt or runtimes[0]
    runtime_mod.list_runtimes = lambda: list(runtimes)
    runtime_mod.get_default_runtime = lambda: runtimes[0]
    sys.modules["core.runtime"] = runtime_mod
    core_pkg.runtime = runtime_mod

    spec = importlib.util.spec_from_file_location(
        "phase4m_energy",
        ROOT / "services" / "energy.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ENERGY_DB_FILE = db_path
    module._HISTORY_SCHEMA_READY = False
    module._HISTORY_LAST_CLEANUP_DAY = None

    return module, saved


def restore(saved):
    for name, value in saved.items():
        if value is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = value


def dynamic_history_checks():
    rt1 = FakeRuntime(
        "tent_1",
        "Zelt 1",
        {
            "heating": {
                "label": "Heizung",
                "available": True,
                "power": 100.0,
                "today": 0.20,
                "total": 10.0,
            },
            "vent": {
                "label": "Ventilator",
                "available": True,
                "power": 50.0,
                "today": 0.10,
                "total": 4.0,
            },
        },
    )
    rt2 = FakeRuntime(
        "tent_2",
        "Zelt 2",
        {
            "heating": {
                "label": "Heizung",
                "available": True,
                "power": 200.0,
                "today": 0.30,
                "total": 8.0,
            },
        },
    )

    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "energy_test.db")
        service, saved = load_service([rt1, rt2], db_path)
        try:
            base = 1_800_000_000

            first = service.record_energy_history(
                [rt1, rt2],
                now=base,
            )
            require(
                first["recorded"] is True
                and first["controller_power"] == 350.0,
                "Erster History-Poll speichert Controller + beide Stationen",
            )

            peaks = service.get_daily_energy_peaks(
                day=service.datetime.datetime.fromtimestamp(base).date().isoformat()
            )
            require(
                peaks["controller"]["power"] == 350.0,
                "Controller-Tagesmaximum wird aus vorhandenen Runtime-Werten gebildet",
            )
            require(
                peaks["stations"]["tent_2"]["power"] == 200.0,
                "Stations-Tagesmaximum bleibt stationsbezogen",
            )
            require(
                peaks["devices"]["tent_1"]["heating"]["power"] == 100.0,
                "Geräte-Tagesmaximum wird separat gespeichert",
            )

            # Gleicher 2-Minuten-Bucket: Verlauf wird aktualisiert, Peak darf
            # bei niedrigerer Leistung nicht sinken.
            rt1.energy_state["heating"]["power"] = 80.0
            rt1.energy_state["vent"]["power"] = 40.0
            rt2.energy_state["heating"]["power"] = 150.0
            service.record_energy_history(
                [rt1, rt2],
                now=base + 30,
            )

            peaks = service.get_daily_energy_peaks(
                day=service.datetime.datetime.fromtimestamp(base).date().isoformat()
            )
            require(
                peaks["controller"]["power"] == 350.0,
                "Tagesmaximum sinkt bei später niedrigerer Leistung nicht",
            )

            # Nächster Bucket + neuer höherer Peak.
            rt2.energy_state["heating"]["power"] = 300.0
            service.record_energy_history(
                [rt1, rt2],
                now=base + 150,
            )
            peaks = service.get_daily_energy_peaks(
                day=service.datetime.datetime.fromtimestamp(base).date().isoformat()
            )
            require(
                peaks["controller"]["power"] == 420.0,
                "Höherer späterer Poll aktualisiert das Tagesmaximum",
            )

            history = service.get_energy_history(
                "24h",
                now=base + 180,
            )
            controller = next(
                s for s in history["series"]
                if s["controller"]
            )
            station_ids = {
                s["tent_id"]
                for s in history["series"]
                if not s["controller"]
            }

            require(
                len(controller["points"]) >= 1,
                "History-API liefert aggregierten Controller-Verlauf",
            )
            require(
                {"tent_1", "tent_2"}.issubset(station_ids),
                "History-API liefert getrennte Stationsserien",
            )

            overview = service.build_energy_overview([rt1, rt2])
            require(
                "max_power_today" in overview["totals"]
                and "max_device_peak_today" in overview["statistics"],
                "Overview integriert Tagesmaximum für UI und Auswertung",
            )

        finally:
            restore(saved)


def main():
    static_checks()
    dynamic_history_checks()
    print("✅ Phase 4M Energie-Historie / Diagramme / Tagesmaximum vollständig")


if __name__ == "__main__":
    main()
