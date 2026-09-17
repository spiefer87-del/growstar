#!/usr/bin/env python3
"""Regression für einheitliche kompakte Stationsumschalter."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    profiles = (ROOT / "templates/profiles.html").read_text(encoding="utf-8")
    settings = (ROOT / "templates/settings.html").read_text(encoding="utf-8")

    for name, template, switcher_id in (
        ("Profilverwaltung", profiles, "profile-tent-switcher"),
        ("Klima & Grenzwerte", settings, "settings-tent-switcher"),
    ):
        require(
            'class="page-station-switch"' in template
            and f'id="{switcher_id}"' in template,
            f"{name} nutzt den kompakten einheitlichen Stationsumschalter",
        )
        require(
            'const TENT_LIST_URL = "/api/tents";' in template
            and "Array.isArray(payload.tents)" in template
            and "option.disabled = !tent.runtime_loaded" in template,
            f"{name} lädt Stationen und Laufzeitstatus aus der Dashboard-Quelle",
        )

    require(
        ".profile-station-switch{" not in profiles
        and "<label for=\"profile-tent-switcher\">Station</label>" not in profiles,
        "Der große Stationsrahmen der Profilverwaltung ist entfernt",
    )
    require(
        "grow_control_tent_settings" in settings
        and 'SETTINGS_PAGE_TEMPLATE.replace("__TENT_ID__"' in settings
        and "window.location.assign(settingsPageUrl(targetTent))" in settings,
        "Klima-Stationswechsel bleibt auf Klima & Grenzwerte",
    )
    require(
        "Ungespeicherte Klima-Einstellungen verwerfen und die Station wechseln?" in settings
        and "select.value = TENT_ID" in settings
        and 'select:not(#settings-tent-switcher)' in settings,
        "Klima-Entwürfe sind geschützt und der Umschalter markiert sie nicht als Änderung",
    )
    require(
        "loadProfileTentSwitcher();" in profiles
        and "loadSettingsTentSwitcher();" in settings,
        "Beide Stationsumschalter werden beim Seitenstart geladen",
    )

    print("✅ PROFILE-SETTINGS.STATION-SWITCHER.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
