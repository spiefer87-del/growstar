from flask import jsonify

from core.config import config, save_config

import datetime
import core.context as ctx

def register(app:

    @app.route("/api/energy")
    def api_energy():
        with ctx.energy_lock:
            return jsonify(energy_state)

    @app.route("/api/energy/reset_total/<device>", methods=["POST"])
    def api_energy_reset_total_device(device):

        config.setdefault("ENERGY_RESET", {})
        config["ENERGY_RESET"][device] = None

        save_config(config)
        refresh_energy_state()

        return {
            "status": "ok",
            "device": device,
            "mode": "total"
        }

    @app.route("/api/energy/reset_today/<device>", methods=["POST"])
    def api_energy_reset_today_device(device):

        config.setdefault("ENERGY_DAY_OFFSET", {})
        config["ENERGY_DAY_OFFSET"][device] = None

        save_config(config)
        refresh_energy_state()

        return {
            "status": "ok",
            "device": device,
            "mode": "today"
        }

    @app.route("/api/energy/reset_total_all", methods=["POST"])
    def api_energy_reset_total_all():

        config.setdefault("ENERGY_RESET", {})

        with ctx.energy_lock:
            snapshot = dict(energy_state)

        for dev, e in snapshot.items():
            raw = float(e.get("raw_total", 0.0))
            config["ENERGY_RESET"][dev] = raw

        config["ENERGY_RESET"].pop("_all", None)

        save_config(config)
        refresh_energy_state()

        print("🧹 ENERGY: Manueller Total-Reset ALL")

        return {
            "status": "ok"
        }

    @app.route("/api/energy/reset_today_all", methods=["POST"])
    def api_energy_reset_today_all():

        today = datetime.date.today().isoformat()

        config.setdefault("ENERGY_DAY_OFFSET", {})

        with ctx.energy_lock:
            snapshot = dict(energy_state)

        for dev, e in snapshot.items():

            raw = float(e.get("raw_total", 0.0))

            config["ENERGY_DAY_OFFSET"][dev] = {
                "day": today,
                "offset": raw
            }

        config["ENERGY_LAST_DAY_RESET"] = today

        save_config(config)
        refresh_energy_state()

        print("🧹 ENERGY: Manueller Today-Reset ALL")

        return {
            "status": "ok"
        }
