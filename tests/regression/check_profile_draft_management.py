#!/usr/bin/env python3
"""Regression für Profilentwürfe, Katalogspeichern und getrennte Aktivierung."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import re
import sys
import tempfile
import threading


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import core.profile as profile
import core.ramp as ramp
from auth.policy import permission_requirement
from core.runtime import TentRuntime


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def sample_profile(day_temp=24.0):
    return {
        "DAY_TEMP": day_temp,
        "NIGHT_TEMP": 20.0,
        "DAY_HUM": 55.0,
        "NIGHT_HUM": 58.0,
        "DAY_TEMP_TOL": 1.0,
        "NIGHT_TEMP_TOL": 1.5,
        "DAY_HUM_TOL": 4.0,
        "NIGHT_HUM_TOL": 5.0,
        "DAY_START_MIN": 360,
        "NIGHT_START_MIN": 1320,
        "RAMP_ENABLED": 1,
        "RAMP_DURATION_MIN": 30,
        "LIGHT_SUN_ENABLED": 0,
        "LIGHT_SUNRISE_DURATION_MIN": 30,
        "LIGHT_SUNSET_DURATION_MIN": 30,
        "LIGHT_SUN_MIN_LEVEL": 11,
    }


def check_ui_contract():
    settings = (ROOT / "templates/settings.html").read_text(encoding="utf-8")
    profiles = (ROOT / "templates/profiles.html").read_text(encoding="utf-8")
    dashboard = (ROOT / "templates/grow_control.html").read_text(encoding="utf-8")
    routes = (ROOT / "routes/tents.py").read_text(encoding="utf-8")
    dashboard_routes = (ROOT / "routes/dashboard.py").read_text(encoding="utf-8")
    policy = (ROOT / "auth/policy.py").read_text(encoding="utf-8")

    for name, template in (("Klima-Seite", settings), ("Profilseite", profiles)):
        element_ids = re.findall(r'\bid="([^"]+)"', template)
        require(
            len(element_ids) == len(set(element_ids)),
            f"{name} besitzt keine doppelten HTML-IDs",
        )

    require(
        'id="save-settings-button"' in settings
        and 'onclick="save()"' in settings,
        "Klima-Seite besitzt einen ausdrücklichen Speichern-Button",
    )
    require(
        'input.addEventListener("change",save)' not in settings
        and "input.value = value;\n    save();" not in settings
        and "async function setProfile" not in settings,
        "Klima-Eingaben und Plus/Minus lösen keinen Live-Save oder Profilwechsel mehr aus",
    )
    require(
        "settingsDirty" in settings
        and 'window.addEventListener("beforeunload"' in settings
        and "Ungespeicherte Änderungen" in settings,
        "Klima-Seite schützt und kennzeichnet ihren lokalen Entwurf",
    )
    require(
        "setLoadInFlight(true)" in settings
        and "setLoadInFlight(false)" in settings
        and "const busy = saveInFlight || loadInFlight" in settings
        and "busy || !configLoaded" in settings,
        "Klima-Eingaben bleiben während des Ladens gegen Überschreiben gesperrt",
    )
    require(
        'id="save-profile-button"' in profiles
        and 'id="activate-profile-button"' in profiles
        and "saveProfile()" in profiles
        and "activateProfile()" in profiles,
        "Profilseite trennt Speichern und Aktivieren sichtbar",
    )
    require(
        'method:"PUT"' in profiles
        and 'method:"POST"' in profiles
        and "Bitte das Profil vor dem Aktivieren zuerst speichern" in profiles,
        "Profilentwurf wird gespeichert, bevor eine getrennte Aktivierung zulässig ist",
    )
    require(
        "requestInFlight || unavailable || dirty" in profiles
        and "setRequestInFlight(true)" in profiles
        and "setRequestInFlight(false)" in profiles,
        "Profilaktivierung und Editor bleiben bei Entwurf oder Ladevorgang sicher gesperrt",
    )
    require(
        "selectProfile(name)" in profiles
        and "PROFILE_ACTIVATE_URL(selectedProfile)" in profiles
        and "button.addEventListener(\"click\",()=>selectProfile(name))" in profiles,
        "Profilauswahl öffnet nur den Editor und aktiviert nicht automatisch",
    )
    require(
        "grow_control_tent_settings" in dashboard
        and "grow_control_tent_profiles" in settings
        and '"profiles.html"' in dashboard_routes
        and "PROFILE_LABELS[state.active_profile]" in dashboard
        and 'safeText("profile-phase", state.profile' in dashboard,
        "Dashboard öffnet zuerst Klima, während die Profilverwaltung erreichbar bleibt",
    )
    require(
        '@app.get("/api/tents/<tent_id>/profiles")' in routes
        and '@app.put("/api/tents/<tent_id>/profiles/<name>")' in routes
        and '"runtime_config_changed": False' in routes,
        "Stations-API bietet Kataloglesen und runtime-freies Profilspeichern",
    )
    require(
        'path.endswith("/profiles")' in policy
        and '"/profiles/" in path' in policy,
        "Profilverwaltung ist in die bestehende Lese-/Schreibberechtigung eingebunden",
    )

    page_read = permission_requirement(
        "/grow-control/tents/tent_1/profiles",
        "GET",
    )
    api_read = permission_requirement(
        "/api/tents/tent_1/profiles",
        "GET",
    )
    api_write = permission_requirement(
        "/api/tents/tent_1/profiles/bloom",
        "PUT",
    )
    require(
        page_read.permissions == ("settings.view",)
        and set(api_read.permissions) == {"grow.view", "settings.view"}
        and api_read.mode == "any"
        and set(api_write.permissions) == {"grow.configure", "settings.manage"}
        and api_write.mode == "any",
        "Profilseite und API verwenden exakt die vorgesehenen Berechtigungen",
    )


def main():
    check_ui_contract()

    original_file = profile.PROFILE_FILE
    original_catalog = deepcopy(profile.PROFILES)
    original_stop_ramp = ramp.stop_ramp

    try:
        with tempfile.TemporaryDirectory(prefix="growstar-profile-regression-") as tmp:
            profile.PROFILE_FILE = str(Path(tmp) / "profiles.json")
            profile.PROFILES.clear()
            profile.PROFILES.update({
                "active": "veg",
                "profiles": {
                    "veg": sample_profile(24.0),
                    "bloom": sample_profile(27.0),
                },
            })

            runtime = TentRuntime(
                tent_id="tent_profile_test",
                name="Profiltest",
                config={
                    "ACTIVE_PROFILE": "veg",
                    "DAY_TEMP": 24.0,
                    "NIGHT_TEMP": 20.0,
                },
                state=SimpleNamespace(
                    ramp_active=True,
                    live_state={
                        "ramp_active": True,
                        "ramp_target": 27.0,
                    },
                ),
                state_lock=threading.RLock(),
            )
            runtime.persist_calls = 0

            def persist_config():
                runtime.persist_calls += 1

            runtime.persist_config = persist_config
            runtime_before_save = deepcopy(runtime.config)

            edited_bloom = sample_profile(28.5)
            saved = profile.update_profile("bloom", edited_bloom)

            require(
                saved["DAY_TEMP"] == 28.5
                and profile.PROFILES["profiles"]["bloom"]["DAY_TEMP"] == 28.5,
                "Nicht aktives Blüteprofil wird im Katalog gespeichert",
            )
            require(
                runtime.config == runtime_before_save
                and runtime.persist_calls == 0
                and runtime.state.ramp_active is True,
                "Profilspeichern verändert weder Runtime noch Rampe",
            )

            on_disk = json.loads(Path(profile.PROFILE_FILE).read_text(encoding="utf-8"))
            require(
                on_disk == profile.PROFILES,
                "Profilkatalog wird vollständig und atomar als gültiges JSON persistiert",
            )

            defensive = profile.profile_catalog()
            defensive["bloom"]["DAY_TEMP"] = -99
            require(
                profile.PROFILES["profiles"]["bloom"]["DAY_TEMP"] == 28.5,
                "Profil-API erhält defensive Katalogkopien",
            )

            before_invalid = deepcopy(profile.PROFILES)
            invalid = sample_profile(27.0)
            invalid["DAY_HUM"] = 101
            try:
                profile.update_profile("bloom", invalid)
            except ValueError:
                pass
            else:
                raise AssertionError("Ungültige Profilwerte wurden akzeptiert")

            require(
                profile.PROFILES == before_invalid,
                "Ungültiger Profilentwurf verändert den gespeicherten Katalog nicht",
            )

            stop_calls = []
            ramp.stop_ramp = lambda runtime=None: stop_calls.append(runtime)

            require(
                profile.apply_profile("bloom", runtime=runtime) is True,
                "Gespeichertes Blüteprofil kann anschließend bewusst aktiviert werden",
            )
            require(
                runtime.config["ACTIVE_PROFILE"] == "bloom"
                and runtime.config["DAY_TEMP"] == 28.5
                and runtime.persist_calls == 1,
                "Erst Aktivieren übernimmt den gespeicherten Entwurf in die Runtime",
            )
            require(
                runtime.state.ramp_active is False
                and runtime.state.live_state["ramp_active"] is False
                and runtime.state.live_state["ramp_target"] is None
                and stop_calls == [runtime],
                "Bewusste Aktivierung behält den bestehenden sicheren Rampen-Reset bei",
            )
    finally:
        ramp.stop_ramp = original_stop_ramp
        profile.PROFILE_FILE = original_file
        profile.PROFILES.clear()
        profile.PROFILES.update(original_catalog)

    print("✅ Growstar 3.15.9 / PROFILE.MANAGEMENT.1 vollständig geprüft")


if __name__ == "__main__":
    main()
