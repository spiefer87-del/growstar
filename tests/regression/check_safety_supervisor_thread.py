#!/usr/bin/env python3
"""Growstar 3.9.5 / Phase 4V.5 – Safety-Supervisor-Thread Regression."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
import threading
import time
import types


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def ok(message):
    print("✅", message)


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    ok(message)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def syntax(rel):
    ast.parse(read(rel), filename=rel)
    ok(f"Python-Syntax {rel}")


def _load_safety_thread_with_stub(fake_run_all):
    """Lädt threads/safety.py ohne produktive Aktor-/Hardware-Imports."""

    stub = types.ModuleType("services.safety")
    stub.run_all_live_safety = fake_run_all

    previous = sys.modules.get("services.safety")
    sys.modules["services.safety"] = stub

    try:
        spec = importlib.util.spec_from_file_location(
            "growstar_395_safety_thread_test",
            ROOT / "threads/safety.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            sys.modules.pop("services.safety", None)
        else:
            sys.modules["services.safety"] = previous


def _test_cycle_ignores_shelly_transport_lock():
    import core.context as ctx

    calls = []

    def fake_run_all_live_safety(*, now=None, enforce=True):
        calls.append((now, enforce))
        return {"ok": True}

    safety_thread = _load_safety_thread_with_stub(fake_run_all_live_safety)

    lock_acquired = threading.Event()

    def hold_shelly_lock():
        with ctx.shelly_lock:
            lock_acquired.set()
            time.sleep(0.45)

    holder = threading.Thread(
        target=hold_shelly_lock,
        daemon=True,
    )
    holder.start()

    require(
        lock_acquired.wait(timeout=1.0),
        "Test-Thread hält den Shelly-Transport-Lock",
    )

    started = time.monotonic()
    result = safety_thread.safety_supervisor_cycle(
        now=12345.0,
        enforce=False,
    )
    elapsed = time.monotonic() - started

    require(
        result == {"ok": True}
        and calls == [(12345.0, False)],
        "Safety-Zyklus delegiert Zeitstempel und Enforce-Flag unverändert",
    )

    require(
        elapsed < 0.20,
        "Safety-Zyklus wartet nicht auf einen fremd gehaltenen Shelly-Lock",
    )

    holder.join(timeout=1.0)


def main():
    for rel in (
        "app.py",
        "threads/safety.py",
        "threads/shelly.py",
        "services/safety.py",
        "core/release.py",
        "tests/regression/check_safety_supervisor_thread.py",
    ):
        syntax(rel)

    from core import release

    require(
        release.GROWSTAR_VERSION == "3.9.5"
        and release.GROWSTAR_INTERNAL_PHASE == "4V.5",
        "Growstar meldet Version 3.9.5 / Phase 4V.5",
    )

    safety_thread_source = read("threads/safety.py")
    shelly_thread_source = read("threads/shelly.py")
    safety_service_source = read("services/safety.py")
    app_source = read("app.py")
    safety_core_source = read("core/safety.py")

    require(
        "SAFETY_INTERVAL = 2.0" in safety_thread_source
        and "safety_supervisor_loop" in safety_thread_source
        and "run_all_live_safety" in safety_thread_source,
        "Dedizierter Safety-Supervisor behält das 2-Sekunden-Intervall",
    )

    require(
        "shelly_lock" not in safety_thread_source
        and "requests" not in safety_thread_source
        and "ShellyAPI" not in safety_thread_source,
        "Safety-Thread besitzt keine direkte Shelly-/Netzwerkabhängigkeit",
    )

    require(
        "run_all_live_safety" not in shelly_thread_source
        and "SAFETY_INTERVAL" not in shelly_thread_source,
        "Shelly-Background besitzt keinen Safety-Heartbeat mehr",
    )

    require(
        '"growstar-safety"' in app_source
        and "safety_supervisor_loop" in app_source
        and '"growstar-shelly"' in app_source,
        "app.py startet Safety- und Shelly-Thread getrennt",
    )

    require(
        app_source.index('"growstar-safety"')
        < app_source.index('"growstar-shelly"'),
        "Safety-Supervisor wird vor dem Shelly-Background gestartet",
    )

    store_pos = safety_service_source.index("store_runtime_safety(rt, snapshot)")
    enforce_pos = safety_service_source.index("_enforce_snapshot(rt, snapshot)")
    require(
        store_pos < enforce_pos,
        "Safety-Heartbeat/Overrides werden vor einer physischen Safe-Off-Aktion gespeichert",
    )

    require(
        "SAFETY_STATUS_STALE_SEC = 6.0" in safety_core_source,
        "Safety-Stale-Grenze bleibt bewusst unverändert bei 6 Sekunden",
    )

    _test_cycle_ignores_shelly_transport_lock()

    print("✅ Phase 4V.5 Safety-Supervisor-Entkopplung vollständig")


if __name__ == "__main__":
    main()
