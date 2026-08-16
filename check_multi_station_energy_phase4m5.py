#!/usr/bin/env python3
"""Phase 4M.5 – Tagesverbrauch seit Tagesreset pro Gerät.

Nur Template-/UI-Prüfung. Keine Hardware- oder Netzwerkzugriffe.
"""

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
        print("✅ Jinja-Syntax Phase 4M.5")

    require(
        "Aktuelle Geräteleistung" in energy
        and "Geräte-Maximum heute" in energy,
        "Bestehende Geräteauswertungen bleiben erhalten",
    )
    require(
        "Tagesverbrauch seit Reset" in energy,
        "Neue Tagesverbrauch-Auswertung ist vorhanden",
    )
    require(
        "automatischen oder manuellen Tagesreset" in energy,
        "Beschriftung erklärt den Reset-Bezug eindeutig",
    )
    require(
        'id="deviceTodayBars"' in energy,
        "Eigener Balkenbereich für Tagesverbrauch ist vorhanden",
    )
    require(
        "const todayItems = [];" in energy
        and "Number(item.today)" in energy,
        "Auswertung verwendet die bestehenden device.today-Werte",
    )
    require(
        "barChart('deviceTodayBars', todayItems, {unit:'kWh', digits:3})" in energy,
        "Tagesverbrauch wird in kWh mit drei Nachkommastellen dargestellt",
    )
    require(
        ".filter(st => !filter || st.tent_id === filter)" in energy,
        "Bestehender Stationsfilter gilt auch für die neue Tagesverbrauch-Auswertung",
    )
    require(
        "Tagesauswertung" in energy
        and "Geräteauswertung" in energy
        and "Anteil am heutigen Verbrauch von ${esc(stationName)}" in energy,
        "Phase-4M.3/4M.4-Auswertungen bleiben erhalten",
    )
    require(
        "/api/energy/history?range=" not in energy,
        "Energieübersicht bleibt ohne History-API",
    )
    require(
        "fetch('/api/energy/overview'" in energy,
        "Neue Auswertung verwendet ausschließlich die bestehende Overview-API",
    )

    print("✅ Phase 4M.5 Tagesverbrauch pro Gerät vollständig")


if __name__ == "__main__":
    main()
