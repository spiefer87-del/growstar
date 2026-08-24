#!/usr/bin/env python3
"""Growstar 3.12.3 / UI.4 regression guard for dashboard controller readback."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    tents = (ROOT / "routes/tents.py").read_text(encoding="utf-8")
    ui = (ROOT / "templates/grow_control.html").read_text(encoding="utf-8")

    require(
        "from core.capability_routing import controller_assignment_for_config" in tents,
        "Dashboard nutzt die bestehende Controller-Zuordnung",
    )
    require(
        "from services.spiderfarmer import device as spiderfarmer_device" in tents,
        "Dashboard nutzt das kanonische Spider-Farmer Read-Model",
    )
    require(
        "def _controller_readback(runtime, device):" in tents,
        "Read-only Controller-Readback-Helfer vorhanden",
    )
    require(
        '"controller_readback": _controller_readback(runtime, device)' in tents,
        "Stations-State liefert Controller-Readback",
    )
    require(
        'effective = observed.get("effective")' in tents,
        "Spider-Farmer effective bleibt die primäre Live-Readback-Quelle",
    )
    require(
        'for field in ("on", "level", "oscillation_level", "mode_type"):' in tents,
        "kanonische Livefelder werden weiterhin aus effective übernommen",
    )
    require(
        'if device_id == "fan":' in tents
        and 'runtime.state.live_state.get("_controller_applied")' in tents,
        "Sendecache-Sonderfall ist auf Ventilator-Oszillation begrenzt",
    )
    require(
        "function controllerDetail(device, controller)" in ui,
        "Dashboard formatiert Controllerwerte",
    )
    require(
        'return `Stufe ${level} · Osz. ${oscillation}`;' in ui,
        "Ventilator zeigt Stufe und Oszillation",
    )
    require(
        'return `Dimmung ${level}`;' in ui,
        "Licht zeigt Dimm-Level",
    )
    require(
        'return `Leistung ${level}`;' in ui,
        "Abluft/Gebläse zeigt Controller-Leistung",
    )
    require(
        "if (on && detail)" in ui and "device.controller_readback" in ui,
        "Controllerdetail erscheint nur bei physisch bestätigtem EIN",
    )

    print("✅ Growstar 3.12.3 / UI.4 Dashboard-Readback vollständig geprüft")


if __name__ == "__main__":
    main()
