"""Spider Farmer PS5/PS10 power-strip write API.

This route is deliberately separate from Shelly and from the existing GGS
controller write path.
"""

from flask import jsonify, request

from services.spiderfarmer import controller as get_spiderfarmer_controller
from services.spiderfarmer_powerstrip import send_outlet_power


def _error(message, status):
    return jsonify({
        "success": False,
        "error": str(message),
    }), int(status)


def _find_outlet(controller, outlet):
    wanted = str(outlet or "").strip().upper()

    for device in controller.get("devices") or []:
        if device.get("kind") != "outlet":
            continue
        for channel in device.get("channels") or []:
            if str(channel.get("channel") or "").strip().upper() == wanted:
                return channel
    return None


def _valid_outlet_channel(channel):
    name = str((channel or {}).get("channel") or "").strip().upper()
    return (
        name.startswith("O")
        and name[1:].isdigit()
        and 1 <= int(name[1:]) <= 10
    )


def _is_power_strip(controller):
    if str((controller or {}).get("prefix") or "").strip().upper() == "PS":
        return True

    for device in (controller or {}).get("devices") or []:
        if device.get("kind") != "outlet":
            continue
        if any(_valid_outlet_channel(item) for item in device.get("channels") or []):
            return True

    return False


def register(app):
    @app.post(
        "/api/spiderfarmer/controllers/<controller_id>/outlets/<outlet>/power"
    )
    def api_spiderfarmer_outlet_power(controller_id, outlet):
        controller = get_spiderfarmer_controller(controller_id)
        if not controller:
            return _error("Spider-Farmer-Gerät nicht gefunden", 404)

        if not _is_power_strip(controller):
            return _error(
                "Dieses Spider-Farmer-Gerät ist kein Power Strip",
                409,
            )

        pid = str(controller.get("pid") or "").strip().upper()
        if not pid:
            return _error("Power-Strip-PID fehlt", 409)

        channel = _find_outlet(controller, outlet)
        if not channel:
            return _error("Steckdosenkanal nicht gefunden", 404)

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or "power" not in payload:
            return _error("JSON-Feld power fehlt", 400)

        try:
            response = send_outlet_power(
                controller_id=controller.get("id"),
                pid=pid,
                outlet=channel.get("channel"),
                power=payload.get("power"),
            )
        except Exception as exc:
            return _error(
                f"Power-Strip-Befehl konnte nicht gesendet werden: {exc}",
                502,
            )

        if not response.get("success"):
            return _error(
                response.get("message")
                or response.get("error")
                or "Spider-Farmer-Bridge hat den Befehl abgelehnt",
                502,
            )

        return jsonify({
            "success": True,
            "status": response.get("status"),
            "controller_id": response.get("controller_id"),
            "pid": response.get("pid"),
            "outlet": response.get("outlet"),
            "power": response.get("power"),
            "verified": bool(response.get("verified")),
        })
