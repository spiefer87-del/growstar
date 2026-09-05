#!/usr/bin/env python3
"""Regression für klassischen VPD-Sollwert und Ernteprognose."""

from datetime import date, timedelta
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parents[2]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.helpers import calculate_target_vpd
import plant_management.database as database


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    require(
        calculate_target_vpd(24.5, 60.0) == 1.23,
        "Der klassische VPD-Sollwert folgt exakt Temperatur- und Feuchte-Sollwert",
    )
    require(
        calculate_target_vpd(None, 60.0) is None
        and calculate_target_vpd(24.5, 101.0) is None,
        "Unvollständige oder ungültige Sollwerte erzeugen keinen falschen VPD",
    )

    dashboard = (ROOT / "templates" / "grow_control.html").read_text(
        encoding="utf-8"
    )
    tent_route = (ROOT / "routes" / "tents.py").read_text(encoding="utf-8")
    require(
        'state.classic_vpd_target' in dashboard
        and 'Soll: ${classicTarget.toFixed(2)} kPa' in dashboard
        and '"classic_vpd_target": calculate_target_vpd(' in tent_route,
        "Die klassische VPD-Kachel zeigt den live berechneten Soll-VPD",
    )

    fixed_today = date(2026, 9, 5)
    forecast = database.calculate_harvest_forecast(
        "2026-09-01",
        63,
        today=fixed_today,
    )
    require(
        forecast["harvest_on"] == "2026-11-03"
        and forecast["harvest_label"] == "03.11.2026"
        and forecast["days_remaining"] == 59
        and forecast["flower_day"] == 5,
        "Blütebeginn plus Sorten-Planwert ergibt Datum, Resttage und Blütetag",
    )
    require(
        database.calculate_harvest_forecast(None, 63, today=fixed_today) is None
        and database.calculate_harvest_forecast("2026-09-01", 0, today=fixed_today) is None,
        "Ohne Blütebeginn oder positiven Planwert wird kein Datum geraten",
    )

    original_db_file = database.DB_FILE
    with tempfile.TemporaryDirectory(prefix="growstar-harvest-test-") as temp_dir:
        database.DB_FILE = Path(temp_dir) / "plants.db"
        try:
            database.init_plant_management_db()
            cultivar_id = database.save_cultivar({
                "code": "TEST-63",
                "name": "Timeline Test",
                "expected_flower_days": 63,
                "active": True,
            })
            flowering_start = date.today() - timedelta(days=10)
            plant_id = database.save_plant({
                "code": "PL-FORECAST",
                "display_name": "Forecast Plant",
                "cultivar_id": cultivar_id,
                "started_on": (flowering_start - timedelta(days=30)).isoformat(),
                "current_stage": "vegetative",
                "status": "active",
            })
            database.set_plant_stage(
                plant_id,
                "flowering",
                started_on=flowering_start.isoformat(),
            )

            plant = database.get_plant(plant_id)
            timeline = database.get_timeline(active_only=True)
            expected_harvest = flowering_start + timedelta(days=63)
            row = timeline["rows"][0]
            require(
                plant["harvest_forecast"]["harvest_on"]
                == expected_harvest.isoformat()
                and row["harvest_forecast"]["harvest_on"]
                == expected_harvest.isoformat(),
                "Pflanzendetail und Timeline verwenden dieselbe dynamische Prognose",
            )
            require(
                timeline["end"] == expected_harvest.isoformat()
                and 0.0 <= row["harvest_forecast"]["harvest_left"] < 100.0
                and row["harvest_forecast"]["width"] > 0.0,
                "Die Timeline erweitert sich bis zur Ernte und positioniert Plan sowie Marker",
            )
        finally:
            database.DB_FILE = original_db_file

    timeline_template = (ROOT / "templates" / "plants" / "timeline.html").read_text(
        encoding="utf-8"
    )
    detail_template = (ROOT / "templates" / "plants" / "plant_detail.html").read_text(
        encoding="utf-8"
    )
    require(
        'class="pm-flower-plan"' in timeline_template
        and 'class="pm-harvest-marker' in timeline_template
        and "row.harvest_forecast.harvest_label" in timeline_template
        and "plant.harvest_forecast.harvest_label" in detail_template,
        "Timeline und Pflanzendetail machen Ernteprognose und Blüteplan sichtbar",
    )

    print("✅ Klassischer VPD-Sollwert und Blüterechner vollständig geprüft")


if __name__ == "__main__":
    main()
