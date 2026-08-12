#!/usr/bin/env python3
"""Growstar Phase 4J – sichere statische Regression für Diagnostics UI."""

from __future__ import annotations

import ast
from pathlib import Path

try:
    from jinja2 import Environment
except ModuleNotFoundError:
    Environment = None


ROOT = Path(__file__).resolve().parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    service = read("services/watchdog.py")
    template = read("templates/watchdog.html")
    diagnostic = read("diagnose_raw_sensor_error.py")
    self_src = read("check_multi_tent_phase4j.py")

    ast.parse(service, filename="services/watchdog.py")
    ast.parse(diagnostic, filename="diagnose_raw_sensor_error.py")
    ast.parse(self_src, filename="check_multi_tent_phase4j.py")
    print("✅ Python-Syntax Phase 4J")

    if Environment is not None:
        Environment().parse(template)
        print("✅ Jinja-Syntax Watchdog")
    else:
        print("ℹ️ Jinja2 nicht installiert – Template-Parser übersprungen")

    check("Betriebsübersicht" in template and "renderSummary" in template,
          "Watchdog besitzt controllerweite Betriebsübersicht")
    check("<span>Safety</span>" in template and "FAILSAFE" in template
          and "SUPERVISOR STALE" in template,
          "Phase-4I-Safety-Anzeige bleibt sichtbar")
    check("Safety-Vorschau / Diagnose" in template,
          "Read-only Safety-Vorschau ist pro Station vorhanden")
    check("/api/watchdog/status" in template,
          "Bestehende Watchdog-Status-API bleibt unverändert")
    check("/api/watchdog/log" in template,
          "Bestehende Watchdog-Log-API bleibt unverändert")
    check("SAFETY_WARN_REPEAT_SEC" in service
          and "SAFETY_SUPERVISOR_WARN_REPEAT_SEC" in service,
          "Safety-Warnungen sind rate-limitiert")
    check("requests." not in service and "switch_shelly" not in service
          and "set_device(" not in service,
          "Watchdog bleibt read-only und schaltet keine Hardware")
    check("import services.hardware" not in diagnostic
          and "from services.hardware" not in diagnostic,
          "Raw-Sensor-Diagnose importiert keinen produktiven Hardware-Service")
    check("import requests" not in diagnostic and "from requests" not in diagnostic,
          "Raw-Sensor-Diagnose sendet keine Netzwerkrequests")
    check("tent_1" not in service and "tent_2" not in service
          and "tent_1" not in template and "tent_2" not in template,
          "Phase 4J enthält keine stationsspezifische Sonderlogik")

    print("✅ Phase 4J Diagnostics UI vollständig")


if __name__ == "__main__":
    main()
