from flask import jsonify
import time

import core.state as state
from core.config import config
from core.devices import get_device_mode


def register(app, get_energy_state):

    @app.route("/api/state")
    def api_state():
        return jsonify({

            # ================= SENSOR =================
            "temp_raw": state.live_state.get("temp_raw"),
            "temp": state.live_state.get("temp"),
            "hum_raw": state.live_state.get("hum_raw"),
            "hum": state.live_state.get("hum"),

            "temp_target": state.live_state.get("temp_target"),
            "temp_tol": state.live_state.get("temp_tol"),
            "hum_target": state.live_state.get("hum_target"),
            "hum_tol": state.live_state.get("hum_tol"),

            "vpd": state.live_state.get("vpd"),

            # ================= PROFILE =================
            "profile": state.current_profile,
            "ramp_active": bool(
                state.ramp_active and config.get("RAMP_ENABLED", 0)
            ),

            # ================= DEVICES =================
            "heating_on": state.heating_on,
            "fan_on": state.fan_on,
            "light_on": state.light_on,
            "vent_on": state.vent_on,

            # Modi
            "heating_mode": get_device_mode("heating"),
            "fan_mode": get_device_mode("fan"),
            "light_mode": get_device_mode("light"),
            "vent_mode": get_device_mode("vent"),

            # ================= ENERGY =================
            "energy": get_energy_state(),

            # ================= SENSOR HEALTH =================
            "temp_ok": not state.temp_stale,
            "hum_ok": not state.hum_stale,

            "temp_age": (
                int(time.time() - state.last_ds_time)
                if state.last_ds_time
                else None
            ),

            "hum_age": (
                int(time.time() - state.last_dht_time)
                if state.last_dht_time
                else None
            ),

            # ================= DEBUG =================
            "device_modes": config.get("DEVICE_MODES", {})
        })
