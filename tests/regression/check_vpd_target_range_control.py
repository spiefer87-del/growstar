#!/usr/bin/env python3
"""Regression für VPD-Klimaziele mit frei einstellbarer Plus/Minus-Range."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
REGRESSION = ROOT / "tests" / "regression"
for path in (ROOT, REGRESSION):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


from check_vpd_hard_humidity_limits import night_runtime
from check_vpd_intelligent_control import set_inside
from core.vpd_control import _temperature_for_vpd_exact, update_vpd_control


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    runtime = night_runtime()
    first = update_vpd_control(runtime, now=1000)
    preferred = first["setpoints"]["preferred"]

    require(
        preferred["temp_center"] == 20.0
        and preferred["temp_range"] == 3.0
        and preferred["hum_center"] == 56.0
        and preferred["hum_range"] == 6.0,
        "Bestehende Min/Max-Werte werden verlustfrei als Zielwert plus Range interpretiert",
    )
    require(
        abs(preferred["temp"] - 17.86) < 0.02
        and abs(preferred["hum"] - 56.0) < 0.02
        and abs(preferred["vpd"] - 0.90) < 0.001,
        "Growstar trifft bei Feuchte-Priorität den Feuchte-Zielwert auf der VPD-Zielkurve",
    )

    former_limit = night_runtime()
    former_limit_temp = _temperature_for_vpd_exact(0.90, 62.0)
    set_inside(former_limit, temp=former_limit_temp, hum=62.0)
    former_limit_plan = update_vpd_control(former_limit, now=2000)
    require(
        0.85 <= former_limit_plan["vpd"] <= 0.95
        and former_limit_plan["direction"] == "raise"
        and former_limit_plan["stage"] == "exhaust"
        and abs(former_limit_plan["effective_hum_target"] - 56.0) < 0.02,
        "62 Prozent ist nur noch die Obergrenze; im VPD-Band regelt Growstar weiter zum gekoppelten Feuchteziel",
    )

    high_vpd_and_hum = night_runtime(temp=23.0, hum=60.0)
    high_plan = update_vpd_control(high_vpd_and_hum, now=3000)
    require(
        high_plan["vpd"] > 0.95
        and high_plan["direction"] == "lower"
        and high_plan["stage"] == "cool"
        and high_plan["actions"]["humidifier"]["power"] is False
        and high_plan["actions"]["dehumidifier"]["power"] is False,
        "Außerhalb des VPD-Bands bleibt die VPD-Richtung führend und startet keinen widersprüchlichen Feuchteaktor",
    )

    reached = night_runtime()
    set_inside(
        reached,
        temp=preferred["temp"],
        hum=preferred["hum"],
    )
    reached_plan = update_vpd_control(reached, now=4000)
    require(
        reached_plan["stage"] == "in_band"
        and reached_plan["direction"] is None
        and reached_plan["actions"]["humidifier"]["power"] is False
        and reached_plan["actions"]["dehumidifier"]["power"] is False,
        "Am gekoppelten Klimaziel hält AUTO stabil, ohne Feuchteaktoren gegeneinander zu schalten",
    )

    settings_page = (ROOT / "templates" / "settings.html").read_text(
        encoding="utf-8"
    )
    profile_page = (ROOT / "templates" / "profiles.html").read_text(
        encoding="utf-8"
    )
    for page, label in ((settings_page, "Einstellungen"), (profile_page, "Profile")):
        require(
            'id="VPD_TEMP_CENTER_DAY"' in page
            and 'id="VPD_TEMP_RANGE_DAY"' in page
            and 'id="VPD_HUM_CENTER_NIGHT"' in page
            and 'id="VPD_HUM_RANGE_NIGHT"' in page
            and 'type="hidden" id="VPD_TEMP_MIN_DAY"' in page
            and "syncVpdBoundsFromWindowEditors" in page
            and "syncVpdWindowEditorsFromBounds" in page,
            f"{label} zeigen Zielwert plus Range und speichern weiterhin kompatible Min/Max-Werte",
        )

    print("✅ VPD-Klimaziele mit Zielwert plus Range vollständig geprüft")


if __name__ == "__main__":
    main()
