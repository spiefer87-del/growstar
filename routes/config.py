from flask import request, jsonify

import core.state as state

from core.config import config, save_config
from core.profile import PROFILES, save_profiles
from core.ramp import (
    stop_ramp,
    resync_active_ramp,
    update_ramp_duration,
)


def register(app):

    @app.route("/api/config", methods=["GET", "POST"])
    def api_config():

        if request.method == "GET":
            return jsonify({
                **config,
                "ACTIVE_PROFILE": PROFILES.get("active")
            })

        data = request.json or {}

        # =========================================
        # CONFIG UPDATE
        # =========================================

        for key, value in data.items():

            # Dashboard
            if key.startswith("DASH_"):
                config[key] = value
                continue

            # Device Modes
            if key == "DEVICE_MODES":
                config.setdefault("DEVICE_MODES", {})
                config["DEVICE_MODES"].update(value)
                continue

            if key == "DEVICE_PARAMS":
                config.setdefault("DEVICE_PARAMS", {})

                for dev, params in value.items():
                    config["DEVICE_PARAMS"].setdefault(dev, {})
                    config["DEVICE_PARAMS"][dev].update(params)

                continue

            if key == "DEVICE_ENV_CONFIG":
                config.setdefault("DEVICE_ENV_CONFIG", {})

                for dev, env in value.items():
                    config["DEVICE_ENV_CONFIG"].setdefault(dev, {})
                    config["DEVICE_ENV_CONFIG"][dev].update(env)

                continue

            # IPs
            if key.startswith("IP_"):
                config[key] = str(value).strip()
                continue

            # Relays
            if key.startswith("RELAY_"):
                try:
                    config[key] = int(value)
                except:
                    pass
                continue

            # Integer
            if key in [
                "ENERGY_DAY_RESET_MIN"
            ]:
                try:
                    config[key] = int(value)
                except:
                    pass
                continue

            # Float / Fallback
            try:
                config[key] = float(value)
            except:
                config[key] = value

        # =========================================
        # Ramp
        # =========================================

        if state.ramp_active:

            if "RAMP_DURATION_MIN" in data:
                update_ramp_duration()

            if (
                "DAY_TEMP" in data
                or "NIGHT_TEMP" in data
            ):
                resync_active_ramp()

        # =========================================
        # Ramp Stop
        # =========================================

        if not config.get("RAMP_ENABLED", 0):

            stop_ramp()

            state.live_state["ramp_active"] = False
            state.live_state["ramp_target"] = None

        # =========================================
        # Save
        # =========================================

        save_config(config)

        # =========================================
        # Mirror Active Profile
        # =========================================

        active = PROFILES.get("active")

        DESIGN_KEYS = {
            "DASH_ENV",
            "DASH_ENV_ORDER",
            "DASH_DEVICE_ORDER",
            "DEVICE_MODES",
            "DEVICE_PARAMS",
            "DEVICE_ENV_CONFIG"
        }

        if active and active in PROFILES.get("profiles", {}):

            profile = PROFILES["profiles"][active]

            for key in profile.keys():
                if key in config and key not in DESIGN_KEYS:
                    profile[key] = config[key]

            save_profiles(PROFILES)

        return jsonify({
            "status": "ok",
            "config": config
        })
