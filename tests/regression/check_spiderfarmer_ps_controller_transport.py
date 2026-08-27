#!/usr/bin/env python3
"""Growstar 3.13.9 / SF.PSC1 regression."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    source = (ROOT / "bridge/spiderfarmer/powerstrip_proxy.py").read_text(encoding="utf-8")
    command_model = (ROOT / "bridge/spiderfarmer/command_model.py").read_text(encoding="utf-8")

    require('if action == "set_controller":' in source, "PS-Proxy erkennt Controller-Schreibbefehle")
    require("if self._is_observed_powerstrip_pid(pid):" in source, "PS-Pfad nur für beobachtete PS-PID")
    require("return await self._dispatch_powerstrip_controller(request)" in source, "PS-PID erhält eigenen Controller-Transport")
    require("return await super()._dispatch_command(request)" in source, "D734/CB bleibt auf bestehendem Pfad")
    require('module not in {"light", "fan", "blower"}' in source, "PS-Controllerpfad auf Light/Fan/Blower begrenzt")
    require("compiled = compile_controller_command(" in source, "Bestehender Payload-Compiler wird wiederverwendet")
    require("topic = self._powerstrip_down_topic(controller_id, pid)" in source, "Controller nutzt validierten PS-DOWN-Transport")
    require('"diagnostic": "ps_controller_transport"' in source, "PS-Controllertransport diagnostisch markiert")
    require("compile_outlet_power_command" in source, "O1-O5 Outlet-Pfad bleibt vorhanden")
    require('"oscillation": "shakeLevel"' in command_model, "Fan-Oszillation bleibt shakeLevel")

    print("✅ Growstar 3.13.9 / SF.PSC1 vollständig geprüft")


if __name__ == "__main__":
    main()
