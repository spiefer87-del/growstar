#!/usr/bin/env python3
"""Regression für Growstar 3.16.17 / PLANT.GUIDE.1."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from plant_management.grow_guides import (
    build_vpd_guide,
    vpd_guide_phase_for_plant,
)


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    guide = build_vpd_guide([])
    require(
        len(guide["phases"]) == 7
        and guide["phases"][0]["id"] == "germination"
        and guide["phases"][-1]["id"] == "flowering_late",
        "Der Leitfaden deckt Keimung bis späte Blüte in sieben Stufen ab",
    )
    require(
        guide["initial_phase_id"] == "vegetative_late"
        and guide["phases"][2]["day"]["calculated"] == 0.895
        and guide["phases"][4]["day"]["calculated"] == 1.204,
        "Beispielklima und VPD werden mit der zentralen Growstar-Formel gekoppelt",
    )

    early_veg, early_veg_reason = vpd_guide_phase_for_plant({
        "current_stage": "vegetative",
        "stage_days": 20,
        "expected_veg_days": 42,
    })
    late_veg, _ = vpd_guide_phase_for_plant({
        "current_stage": "vegetative",
        "stage_days": 21,
        "expected_veg_days": 42,
    })
    require(
        early_veg == "vegetative_early"
        and late_veg == "vegetative_late"
        and "Sorten-Planwert" in early_veg_reason,
        "Die Vegetation wird am individuellen Planwert nachvollziehbar geteilt",
    )

    flower_phases = [
        vpd_guide_phase_for_plant({
            "current_stage": "flowering",
            "stage_days": stage_days,
            "expected_flower_days": 63,
        })[0]
        for stage_days in (22, 23, 48)
    ]
    require(
        flower_phases == ["flowering_early", "flowering_mid", "flowering_late"],
        "Frühe, mittlere und späte Blüte folgen dem Sorten-Blütefortschritt",
    )

    populated = build_vpd_guide([
        {
            "id": 1,
            "code": "PL-1",
            "display_name": "Blüte A",
            "current_stage": "flowering",
            "stage_label": "Blüte",
            "stage_days": 10,
            "expected_flower_days": 63,
        },
        {
            "id": 2,
            "code": "PL-2",
            "display_name": "Blüte B",
            "current_stage": "flowering",
            "stage_label": "Blüte",
            "stage_days": 12,
            "expected_flower_days": 63,
        },
        {
            "id": 3,
            "code": "PL-3",
            "display_name": "Vegetation A",
            "current_stage": "vegetative",
            "stage_label": "Vegetation",
            "stage_days": 30,
            "expected_veg_days": 42,
        },
    ])
    counts = {phase["id"]: phase["active_count"] for phase in populated["phases"]}
    require(
        populated["active_plant_count"] == 3
        and populated["initial_phase_id"] == "flowering_early"
        and counts["flowering_early"] == 2
        and counts["vegetative_late"] == 1,
        "Aktive Pflanzen markieren die passende Leitfadenzeile und Vorauswahl",
    )

    route = (ROOT / "routes" / "plant_management.py").read_text(encoding="utf-8")
    page = (ROOT / "templates" / "plants" / "cultivation_guide.html").read_text(
        encoding="utf-8"
    )
    local_nav = (ROOT / "templates" / "plants" / "_nav.html").read_text(
        encoding="utf-8"
    )
    app_nav = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    dashboard = (ROOT / "templates" / "plants" / "dashboard.html").read_text(
        encoding="utf-8"
    )
    css = (ROOT / "static" / "css" / "plant-management.css").read_text(
        encoding="utf-8"
    )

    require(
        '@app.route("/pflanzenmanagement/anbauhilfe")' in route
        and "build_vpd_guide(list_plants(status=\"active\"))" in route
        and "cultivation_guide" in local_nav
        and "cultivation_guide" in app_nav
        and "VPD-Anbauhilfe" in dashboard,
        "Route, Pflanzen-Navigation, App-Menü und Dashboard verlinken die Anbauhilfe",
    )
    require(
        'id="guide-phase-select"' in page
        and 'id="guide-tent-select"' in page
        and 'fetch("/api/tents"' in page
        and "/state`" in page
        and "window.setInterval(loadTentState, 15000)" in page
        and "Nur Anzeige" in page
        and "textContent" in page
        and "innerHTML" not in page,
        "Phasenwahl und Live-Zeltvergleich aktualisieren sicher und schreibgeschützt",
    )
    require(
        "Luft-VPD und Blatt-VPD" in page
        and "Eine pauschale Feuchte unter 40 % ist kein universelles Ziel" in page
        and ".pm-guide-controls" in css
        and "@media (max-width: 640px)" in css,
        "Fachliche Grenzen und mobiles Layout sind in der Oberfläche sichtbar",
    )

    ids = re.findall(r'id="([^"]+)"', page)
    require(
        len(ids) == len(set(ids)),
        "Die neue Seite enthält keine doppelten HTML-IDs",
    )

    print("✅ Growstar 3.16.17 / PLANT.GUIDE.1 vollständig geprüft")


if __name__ == "__main__":
    main()
