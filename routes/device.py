from flask import request, jsonify

from core.config import config, save_config


def register(app):

    @app.route("/api/device/<device>", methods=["GET", "POST"])
    def api_device(device):

        config.setdefault("DEVICE_MODES", {})
        config.setdefault("DEVICE_PARAMS", {})

        if request.method == "GET":
            return jsonify({
                "mode": config["DEVICE_MODES"].get(device, "OFF"),
                "params": config["DEVICE_PARAMS"].get(device, {})
            })

        data = request.json or {}

        mode = data.get("mode")
        params = data.get("params", {})

        if mode:
            config["DEVICE_MODES"][device] = mode

        config["DEVICE_PARAMS"].setdefault(device, {}).update(params)

        save_config(config)

        return {"status": "ok"}

    @app.route("/api/device/mode/<device>", methods=["POST"])
    def api_set_device_mode(device):

        data = request.json or {}

        config.setdefault("DEVICE_MODES", {})
        config.setdefault("DEVICE_ENV_CONFIG", {})

        if "DEVICE_MODES" in data:
            config["DEVICE_MODES"][device] = data["DEVICE_MODES"][device]

        if "DEVICE_ENV_CONFIG" in data:
            config["DEVICE_ENV_CONFIG"][device] = data["DEVICE_ENV_CONFIG"][device]

        save_config(config)

        return {"status": "ok"}
