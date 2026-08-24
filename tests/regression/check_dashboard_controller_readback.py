#!/usr/bin/env python3
"""Growstar 3.12.0 / UI.1 regression guard."""

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
        "UI.1 nutzt die bestehende Controller-Zuordnung",
    )
    require(
        "from services.spiderfarmer import device as spiderfarmer_device" in tents,
        "UI.1 nutzt das kanonische Spider-Farmer Read-Model",
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
        "function controllerDetail(device, controller)" in ui,
        "Dashboard formatiert Controller-Livewerte",
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
        "if (on && detail)" in ui
        and "device.controller_readback" in ui,
        "Livewert erscheint nur bei physisch bestätigtem EIN",
    )
    require(
        "_controller_applied" not in tents,
        "Dashboard verwendet nicht den Controller-Sendecache",
    )

    print("✅ Growstar 3.12.0 / UI.1 vollständig geprüft")


if __name__ == "__main__":
    main()
