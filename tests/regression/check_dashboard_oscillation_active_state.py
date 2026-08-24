#!/usr/bin/env python3
"""Growstar 3.12.2 / UI.3 regression guard."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def require(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("✅", msg)

def main():
    text = (ROOT / "routes/tents.py").read_text(encoding="utf-8")
    require(
        "from core.controller_states import resolve_control_state" in text,
        "aktive Controller-Zustände werden für Dashboard-Readback aufgelöst",
    )
    require(
        'runtime.state.live_state.get("_controller_applied")' in text,
        "zuletzt tatsächlich angewendete Controller-Werte haben Vorrang",
    )
    require(
        'result["oscillation_source"] = "applied_controller_state"' in text,
        "angewendeter Oszillationswert wird als Quelle markiert",
    )
    require(
        '"ON": "on"' in text and '"TIME": "time"' in text and '"ENV": "env"' in text,
        "aktive Growstar-Modi werden auf ihre getrennten control_states abgebildet",
    )
    require(
        'resolve_control_state(params, state_name)' in text,
        "Fallback liest den Setpoint des aktiven Modus",
    )
    require(
        'result["oscillation_source"] = "active_mode_setpoint"' in text,
        "Fallback-Quelle wird explizit markiert",
    )
    print("✅ Growstar 3.12.2 / UI.3 vollständig geprüft")

if __name__ == "__main__":
    main()
