#!/usr/bin/env python3
"""Regression für Stationswert-Kopie, Sonnenprofil und sichere Aktivierung."""

from copy import deepcopy
import json
from pathlib import Path
import re
from types import SimpleNamespace
import sys
import tempfile
import threading


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import core.profile as profile
import core.ramp as ramp
from core.runtime import TentRuntime


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def sample_profile(day_temp=24.0, *, sun_enabled=0):
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
        "RAMP_DURATION_MIN": 35,
        "LIGHT_SUN_ENABLED": sun_enabled,
        "LIGHT_SUNRISE_DURATION_MIN": 25,
        "LIGHT_SUNSET_DURATION_MIN": 40,
        "LIGHT_SUN_MIN_LEVEL": 14,
    }


def check_ui_contract():
    dashboard = (ROOT / "templates/grow_control.html").read_text(encoding="utf-8")
    settings = (ROOT / "templates/settings.html").read_text(encoding="utf-8")
    profiles = (ROOT / "templates/profiles.html").read_text(encoding="utf-8")
    routes = (ROOT / "routes/tents.py").read_text(encoding="utf-8")
    core_profile = (ROOT / "core/profile.py").read_text(encoding="utf-8")

    profile_link = re.search(
        r'<a href="\{\{ url_for\(\'grow_control_tent_settings\'.*?'
        r'id="profile-card"',
        dashboard,
        re.DOTALL,
    )
    require(
        profile_link is not None
        and "grow_control_tent_profiles" in settings,
        "Dashboard-Profilkarte öffnet zuerst Klima & Grenzwerte",
    )

    require(
        'id="copy-current-button"' in profiles
        and "async function copyCurrentSettings()" in profiles
        and "payload.current_settings" in profiles
        and "markDirty:true" in profiles,
        "Aktuelle Stationswerte werden nur in den ausgewählten Profilentwurf kopiert",
    )
    require(
        "Bitte Profil speichern" in profiles
        and "PROFILE_SAVE_URL(selectedProfile)" in profiles,
        "Kopierte Stationswerte benötigen weiterhin eine bewusste Profilspeicherung",
    )

    for field_id in (
        "RAMP_ENABLED",
        "RAMP_DURATION_MIN",
        "LIGHT_SUN_ENABLED",
        "LIGHT_SUNRISE_DURATION_MIN",
        "LIGHT_SUNSET_DURATION_MIN",
        "LIGHT_SUN_MIN_LEVEL",
    ):
        require(
            f'id="{field_id}"' in profiles,
            f"Profilverwaltung enthält {field_id}",
        )

    require(
        "result.RAMP_ENABLED" in profiles
        and "result.LIGHT_SUN_ENABLED" in profiles
        and "profile.LIGHT_SUN_ENABLED" in profiles,
        "Rampe und Sonnenverlauf werden geladen und vollständig gespeichert",
    )
    require(
        ".actions{position:static}" in profiles,
        "Mobile Profilaktionen verdecken die Profilfelder nicht mehr dauerhaft",
    )
    require(
        '"current_settings": profile_settings_from_config(runtime.config)' in routes
        and '"current_settings_scope": "station"' in routes,
        "Profil-API liefert einen stationsbezogenen kopierbaren Snapshot",
    )
    require(
        "except ProfileActivationError as exc" in routes
        and "light_sun_controller_required" in core_profile,
        "Sonnenprofil-Aktivierung besitzt einen serverseitigen Controller-Schutz",
    )


def main():
    check_ui_contract()

    original_file = profile.PROFILE_FILE
    original_catalog = deepcopy(profile.PROFILES)
    original_stop_ramp = ramp.stop_ramp

    try:
        with tempfile.TemporaryDirectory(prefix="growstar-profile-copy-") as tmp:
            profile.PROFILE_FILE = str(Path(tmp) / "profiles.json")

            legacy_veg = sample_profile(24.0)
            legacy_bloom = sample_profile(27.0)
            for settings in (legacy_veg, legacy_bloom):
                for key in profile.PROFILE_COMPATIBILITY_DEFAULTS:
                    settings.pop(key)

            legacy_catalog = {
                "active": "veg",
                "profiles": {
                    "veg": legacy_veg,
                    "bloom": legacy_bloom,
                },
            }
            Path(profile.PROFILE_FILE).write_text(
                json.dumps(legacy_catalog),
                encoding="utf-8",
            )

            loaded = profile.load_profiles()
            require(
                loaded["profiles"]["veg"]["LIGHT_SUN_ENABLED"] == 0
                and loaded["profiles"]["veg"]["LIGHT_SUN_MIN_LEVEL"] == 11,
                "Alte Profile erhalten sichere Sonnenverlauf-Standardwerte",
            )
            unchanged_disk = json.loads(
                Path(profile.PROFILE_FILE).read_text(encoding="utf-8")
            )
            require(
                "LIGHT_SUN_ENABLED" not in unchanged_disk["profiles"]["veg"],
                "Kompatibilitätswerte werden beim Laden nicht ungefragt persistiert",
            )

            profile.PROFILES.clear()
            profile.PROFILES.update(loaded)

            current_config = sample_profile(25.4, sun_enabled=1)
            current_config.update({
                "ACTIVE_PROFILE": "veg",
                "RAMP_DURATION_MIN": 45,
                "LIGHT_SUNRISE_DURATION_MIN": 35,
                "LIGHT_SUNSET_DURATION_MIN": 50,
                "LIGHT_SUN_MIN_LEVEL": 17,
            })
            runtime = TentRuntime(
                tent_id="tent_profile_copy_test",
                name="Profilkopietest",
                config=deepcopy(current_config),
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
            runtime.persist_config = lambda: setattr(
                runtime,
                "persist_calls",
                runtime.persist_calls + 1,
            )

            snapshot = profile.profile_settings_from_config(runtime.config)
            require(
                set(snapshot) == set(profile.PROFILE_SETTING_KEYS)
                and snapshot["DAY_TEMP"] == 25.4
                and snapshot["RAMP_DURATION_MIN"] == 45
                and snapshot["LIGHT_SUN_ENABLED"] == 1
                and snapshot["LIGHT_SUNSET_DURATION_MIN"] == 50,
                "Stations-Snapshot enthält Klima, Zeiten, Rampe und Sonnenverlauf",
            )

            runtime_before_save = deepcopy(runtime.config)
            saved = profile.update_profile("bloom", snapshot)
            require(
                saved == snapshot
                and profile.PROFILES["profiles"]["bloom"] == snapshot,
                "Stationswerte lassen sich als ausgewählte Profilvorlage speichern",
            )
            require(
                runtime.config == runtime_before_save
                and runtime.persist_calls == 0
                and runtime.state.ramp_active is True,
                "Kopieren und Profilspeichern verändern die laufende Station nicht",
            )

            invalid = deepcopy(snapshot)
            invalid["LIGHT_SUN_MIN_LEVEL"] = 10
            before_invalid = deepcopy(profile.PROFILES)
            try:
                profile.update_profile("bloom", invalid)
            except ValueError:
                pass
            else:
                raise AssertionError("Ungültige Sonnenleistung wurde akzeptiert")
            require(
                profile.PROFILES == before_invalid,
                "Ungültige Sonnenprofilwerte verändern den Katalog nicht",
            )

            stop_calls = []
            ramp.stop_ramp = lambda runtime=None: stop_calls.append(runtime)
            blocked_config = deepcopy(runtime.config)
            try:
                profile.apply_profile("bloom", runtime=runtime)
            except profile.ProfileActivationError as exc:
                require(
                    exc.code == "light_sun_controller_required",
                    "Sonnenprofil ohne Lichtcontroller liefert einen eindeutigen Fehler",
                )
            else:
                raise AssertionError("Sonnenprofil wurde ohne Lichtcontroller aktiviert")

            require(
                runtime.config == blocked_config
                and runtime.persist_calls == 0
                and stop_calls == []
                and runtime.state.ramp_active is True,
                "Blockierte Aktivierung verändert weder Config noch Rampe",
            )

            runtime.config["CONTROLLER_ASSIGNMENTS"] = {
                "light": {
                    "provider": "spiderfarmer",
                    "target_id": "light-controller-test",
                }
            }
            require(
                profile.apply_profile("bloom", runtime=runtime) is True,
                "Sonnenprofil kann mit zugewiesenem Lichtcontroller aktiviert werden",
            )
            require(
                runtime.config["ACTIVE_PROFILE"] == "bloom"
                and runtime.config["RAMP_DURATION_MIN"] == 45
                and runtime.config["LIGHT_SUN_ENABLED"] == 1
                and runtime.config["LIGHT_SUNRISE_DURATION_MIN"] == 35
                and runtime.config["LIGHT_SUNSET_DURATION_MIN"] == 50
                and runtime.config["LIGHT_SUN_MIN_LEVEL"] == 17
                and runtime.persist_calls == 1,
                "Aktivierung übernimmt Rampe und vollständigen Sonnenverlauf",
            )
            require(
                runtime.state.ramp_active is False
                and runtime.state.live_state["ramp_active"] is False
                and runtime.state.live_state["ramp_target"] is None
                and stop_calls == [runtime],
                "Erfolgreiche Aktivierung behält den sicheren Rampen-Reset bei",
            )
    finally:
        ramp.stop_ramp = original_stop_ramp
        profile.PROFILE_FILE = original_file
        profile.PROFILES.clear()
        profile.PROFILES.update(original_catalog)

    print("✅ Growstar 3.15.10 / PROFILE.MANAGEMENT.2 vollständig geprüft")


if __name__ == "__main__":
    main()
