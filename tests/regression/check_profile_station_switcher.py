#!/usr/bin/env python3
"""Regression für den stationsbezogenen Umschalter der Profilverwaltung."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    template = (ROOT / "templates/profiles.html").read_text(encoding="utf-8")

    require(
        'id="profile-tent-switcher"' in template
        and "Grow-Station für die Profilverwaltung wechseln" in template,
        "Profilverwaltung besitzt einen eindeutig beschrifteten Stationsumschalter",
    )
    require(
        'const TENT_LIST_URL = "/api/tents";' in template
        and "async function loadProfileTentSwitcher()" in template
        and "Array.isArray(payload.tents)" in template,
        "Umschalter lädt dieselbe stationsbezogene Laufzeitliste wie das Dashboard",
    )
    require(
        "grow_control_tent_profiles" in template
        and 'PROFILE_PAGE_TEMPLATE.replace("__TENT_ID__"' in template
        and "window.location.assign(profilePageUrl(targetTent))" in template,
        "Stationswechsel bleibt auf der Profilverwaltung der gewählten Station",
    )
    require(
        "option.disabled = !tent.runtime_loaded" in template
        and 'option.selected = tent.id === TENT_ID' in template,
        "Aktuelle Station ist markiert und nicht geladene Stationen bleiben gesperrt",
    )
    require(
        "Ungespeicherte Profiländerungen verwerfen und die Station wechseln?" in template
        and "select.value = TENT_ID" in template
        and "dirty = false;" in template,
        "Offene Profilentwürfe werden vor einem Stationswechsel geschützt",
    )
    require(
        "loadProfileTentSwitcher();" in template
        and "loadProfiles();" in template,
        "Stationsumschalter und Profile werden beim Seitenstart geladen",
    )

    print("✅ PROFILE.STATION-SWITCHER.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
