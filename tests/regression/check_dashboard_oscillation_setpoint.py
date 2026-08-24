#!/usr/bin/env python3
"""Growstar 3.12.3 / UI.4 regression guard.

Historical UI.2 invariant, updated for the UI.3 architecture:
GGS getDevSta exposes fan.level but no live shakeLevel. Therefore Grow Control
must never present an old observed setConfigField shakeLevel as current live
oscillation. UI.3 resolves oscillation from the successfully applied controller
state, with the active Growstar mode setpoint as restart fallback.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    routes = (ROOT / "routes/tents.py").read_text(encoding="utf-8")
    state_model = (ROOT / "bridge/spiderfarmer/state_model.py").read_text(encoding="utf-8")

    require(
        'if device_id == "fan":' in routes,
        "Oszillations-Fallback ist ausschließlich auf Spider-Farmer fan begrenzt",
    )
    require(
        'runtime.state.live_state.get("_controller_applied")' in routes,
        "zuletzt erfolgreich angewendeter Controller-Zustand wird bevorzugt",
    )
    require(
        'result["oscillation_source"] = "applied_controller_state"' in routes,
        "angewendeter Controller-Zustand ist als Quelle markiert",
    )
    require(
        "resolve_control_state(params, state_name)" in routes,
        "Restart-Fallback liest den Controllerwert des aktiven Growstar-Modus",
    )
    require(
        'result["oscillation_source"] = "active_mode_setpoint"' in routes,
        "aktive Modus-Konfiguration ist als Fallback-Quelle markiert",
    )
    require(
        'result.pop("oscillation_level", None)' in routes,
        "alter Config-Wert wird ohne gültige Quelle nicht als Livewert ausgegeben",
    )
    require(
        '"shakeLevel": "oscillation_level"' in state_model,
        "beobachtete setConfigField-Konfiguration bleibt diagnostisch im Read-Model erhalten",
    )

    live_section = state_model.split("def _normalize_live_module", 1)[1].split(
        "def _normalize_fan_config", 1
    )[0]
    require(
        '"shakeLevel": "oscillation_level"' not in live_section,
        "getDevSta-Live-Normalisierung behauptet weiterhin keinen shakeLevel",
    )

    print("✅ Growstar 3.12.3 / UI.4 Oszillations-Invariante vollständig geprüft")


if __name__ == "__main__":
    main()
