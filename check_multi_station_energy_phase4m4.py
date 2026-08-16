#!/usr/bin/env python3
"""Phase 4M.4 – Aktoranteil am heutigen Stationsverbrauch."""
from pathlib import Path

try:
    from jinja2 import Environment
except ModuleNotFoundError:
    Environment = None

ROOT = Path(__file__).resolve().parent

def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)

def main():
    energy = (ROOT / "templates" / "energie.html").read_text(encoding="utf-8")

    if Environment is not None:
        Environment().parse(energy)
        print("✅ Jinja-Syntax Phase 4M.4")

    require("Anteil am heutigen Gesamtverbrauch" in energy,
            "Bestehender Stationsanteil am Gesamtverbrauch bleibt erhalten")
    require("Anteil am heutigen Verbrauch von ${esc(stationName)}" in energy,
            "Jeder Aktor zeigt seinen Anteil am heutigen Stationsverbrauch")
    require("function deviceTodaySharePct(item, stationToday)" in energy,
            "Aktoranteil besitzt eine eigene robuste Berechnung")
    require("deviceToday / stationTotal * 100" in energy,
            "Aktoranteil wird aus heutigen Aktor-kWh und Stations-kWh berechnet")
    require("deviceRow(device, item, price, totals.today, st.name)" in energy,
            "Jeder Aktor erhält Stationsverbrauch und Stationsname")
    require("Math.max(0, Math.min(100" in energy,
            "Prozentwerte werden auf 0 bis 100 begrenzt")
    require("<span>nicht verfügbar</span>" in energy,
            "Offline-Messpunkte erfinden keinen Prozentwert")
    require("/api/energy/history?range=" not in energy,
            "Energieübersicht bleibt frei von History-Diagramm-Requests")
    require("fetch('/api/energy/overview'" in energy,
            "Visualisierung nutzt nur die bestehende Overview-API")

    print("✅ Phase 4M.4 Aktoranteile pro Station vollständig")

if __name__ == "__main__":
    main()
