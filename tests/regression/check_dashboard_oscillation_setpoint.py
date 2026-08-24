#!/usr/bin/env python3
"""Growstar 3.12.1 / UI.2 regression guard.

The GGS getDevSta live payload exposes fan.level but no live shakeLevel.
Therefore the Grow-Control dashboard must not present an old observed config
shakeLevel as current oscillation. It uses the station's persisted controller
setpoint for oscillation while keeping fan.level as real readback.
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
        "from core.controller_setpoints import stored_controller_setpoints" in routes,
        "stationsbezogene Controller-Setpoints werden gelesen",
    )
    require(
        'if device_id == "fan":' in routes,
        "Oszillations-Fallback ist ausschließlich auf Spider-Farmer fan begrenzt",
    )
    require(
        'configured = stored_controller_setpoints(params)' in routes,
        "persistierter Controller-Setpoint wird verwendet",
    )
    require(
        'result["oscillation_level"] = configured["oscillation"]' in routes,
        "Dashboard-Readback erhält die konfigurierte Oszillation",
    )
    require(
        'result["oscillation_source"] = "configured_setpoint"' in routes,
        "Quelle der Oszillation wird explizit markiert",
    )
    require(
        'result.pop("oscillation_level", None)' in routes,
        "alter Config-Wert wird ohne gespeicherten Setpoint nicht als Livewert ausgegeben",
    )
    require(
        '"shakeLevel": "oscillation_level"' in state_model,
        "beobachtete setConfigField-Konfiguration bleibt im Read-Model erhalten",
    )
    require(
        '"shakeLevel": "oscillation_level"' not in state_model.split("def _normalize_live_module", 1)[1].split("def _normalize_fan_config", 1)[0],
        "getDevSta-Live-Normalisierung behauptet weiterhin keinen shakeLevel",
    )

    print("✅ Growstar 3.12.1 / UI.2 Oszillationsanzeige vollständig geprüft")


if __name__ == "__main__":
    main()
