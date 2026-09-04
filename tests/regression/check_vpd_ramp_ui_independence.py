#!/usr/bin/env python3
"""Regression für eigenständige VPD-Rampe und AUTO-Sollwertsperre."""

from copy import deepcopy
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.config import DEFAULT_CONFIG
from core.vpd import calculate_vpd_schedule, validate_vpd_environment_alignment


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg.update({
        "DAY_START_MIN": 360,
        "NIGHT_START_MIN": 1320,
        "RAMP_ENABLED": 1,
        "RAMP_DURATION_MIN": 60,
        "LIGHT_SUN_ENABLED": 0,
        "LIGHT_SUNRISE_DURATION_MIN": 5,
        "LIGHT_SUNSET_DURATION_MIN": 180,
        "MIN_TEMP": 10.0,
        "MAX_TEMP": 35.0,
        "MIN_HUM": 0.0,
        "MAX_HUM": 95.0,
    })
    settings = validate_vpd_environment_alignment(cfg)

    without_light, ramp_without_light = calculate_vpd_schedule(
        settings,
        cfg,
        "TAG",
        now_min=390,
    )
    with_light_cfg = deepcopy(cfg)
    with_light_cfg.update({
        "LIGHT_SUN_ENABLED": 1,
        "LIGHT_SUNRISE_DURATION_MIN": 180,
        "LIGHT_SUNSET_DURATION_MIN": 5,
    })
    with_light, ramp_with_light = calculate_vpd_schedule(
        settings,
        with_light_cfg,
        "TAG",
        now_min=390,
    )

    require(
        ramp_without_light["active"] is True
        and ramp_without_light["kind"] == "morning"
        and ramp_without_light["start_min"] == 360
        and ramp_without_light["end_min"] == 420,
        "VPD-Rampe läuft ohne aktivierten Sonnenverlauf am Tag-Start",
    )
    require(
        without_light == with_light
        and ramp_without_light == ramp_with_light,
        "Lichtschalter und Dimmzeiten verändern den VPD-Rampenplan nicht",
    )

    settings_page = (ROOT / "templates/settings.html").read_text(encoding="utf-8")
    profiles_page = (ROOT / "templates/profiles.html").read_text(encoding="utf-8")

    require(
        settings_page.count('id="RAMP_ENABLED"') == 1
        and settings_page.count('id="RAMP_DURATION_MIN"') == 1
        and settings_page.index('id="vpd-control-card"')
        < settings_page.index('id="vpd-ramp-settings"')
        < settings_page.index('id="light-sun-card"'),
        "Eigener VPD-Rampenschalter und Rampenzeit stehen direkt im VPD-Bereich",
    )
    require(
        "vollständig von Helligkeitssensor und Sonnenverlauf" in settings_page
        and "Unabhängig von Licht-Dimmung und Helligkeitssensor" in settings_page
        and 'id="profile-vpd-ramp-settings"' in profiles_page,
        "Klima- und Profilseite erklären die Unabhängigkeit der VPD-Rampe",
    )

    temperature_block = re.search(
        r'id="classic-temperature-controls".*?<div class="divider">',
        settings_page,
        flags=re.DOTALL,
    )
    humidity_block = re.search(
        r'id="classic-humidity-controls".*?<div class="divider">',
        settings_page,
        flags=re.DOTALL,
    )
    require(
        temperature_block is not None
        and all(
            field in temperature_block.group(0)
            for field in ("DAY_TEMP", "DAY_TEMP_TOL", "NIGHT_TEMP", "NIGHT_TEMP_TOL")
        )
        and "MIN_TEMP" not in temperature_block.group(0)
        and humidity_block is not None
        and all(
            field in humidity_block.group(0)
            for field in ("DAY_HUM", "DAY_HUM_TOL", "NIGHT_HUM", "NIGHT_HUM_TOL")
        )
        and "MIN_HUM" not in humidity_block.group(0),
        "Nur klassische Sollwerte sind sperrbar; Schutzgrenzen bleiben separat",
    )
    require(
        'const automatic = mode === "AUTO";' in settings_page
        and 'control.closest?.("[data-classic-control]")' in settings_page
        and 'block.classList.toggle("vpd-locked",automatic)' in settings_page
        and "Alarm- und Schutzgrenzen bleiben einstellbar" in settings_page,
        "Nur AUTO blendet klassische Temperatur- und Feuchteregler aus und sperrt sie",
    )
    require(
        'el("RAMP_DURATION_MIN").min = 0;' in settings_page
        and 'el("RAMP_ENABLED").checked && num("RAMP_DURATION_MIN") < 5' in settings_page,
        "Eine alte Null-Dauer bleibt bei AUS gültig und wird bei aktiver Rampe blockiert",
    )

    vpd_source = (ROOT / "core/vpd.py").read_text(encoding="utf-8")
    schedule_source = vpd_source[
        vpd_source.index("def calculate_vpd_schedule"):
        vpd_source.index("def reset_vpd_control")
    ]
    require(
        'cfg.get("RAMP_DURATION_MIN"' in schedule_source
        and 'cfg.get("RAMP_ENABLED"' in schedule_source
        and 'cfg.get("LIGHT_SUN' not in schedule_source,
        "Regelkern besitzt keine versteckte Abhängigkeit von der Lichtfunktion",
    )

    print("✅ Growstar 3.16.6 / VPD.UI.1 vollständig geprüft")


if __name__ == "__main__":
    main()
