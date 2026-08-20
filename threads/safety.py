"""Dedizierter Safety-Supervisor-Thread.

Phase 4V.5 entkoppelt den Safety-Heartbeat vollständig vom Shelly-/Energy-
Background. Die normale Safety-Auswertung liest ausschließlich Runtime-State,
Sensor-Freshness und den bereits vorhandenen Aktor-Health-Cache.

Nur wenn eine echte Safe-Off-Aktion nötig ist, läuft der Schreibzugriff über
services.safety -> core.actuators. Dort greift weiterhin der Shelly-Transport-
Lock aus Phase 4V.4.
"""

from __future__ import annotations

import time

from services.safety import run_all_live_safety


SAFETY_INTERVAL = 2.0
SAFETY_MIN_SLEEP = 0.05


def safety_supervisor_cycle(*, now=None, enforce=True):
    """Führt genau einen stationsübergreifenden Safety-Zyklus aus."""

    now = time.time() if now is None else float(now)
    return run_all_live_safety(
        now=now,
        enforce=enforce,
    )


def safety_supervisor_loop():
    """Hält den Safety-Heartbeat unabhängig von Shelly-/Energy-Polls frisch."""

    while True:
        started = time.monotonic()

        try:
            safety_supervisor_cycle(enforce=True)
        except Exception as exc:
            # run_all_live_safety isoliert bereits Fehler einzelner Stationen.
            # Dieser Guard schützt zusätzlich den dedizierten Supervisor-Thread
            # gegen einen unerwarteten controllerweiten Ausnahmefall.
            print("❌ Safety Supervisor Thread Fehler:", exc)

        elapsed = max(
            0.0,
            time.monotonic() - started,
        )

        time.sleep(
            max(
                SAFETY_MIN_SLEEP,
                SAFETY_INTERVAL - elapsed,
            )
        )
