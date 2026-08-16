import core.context as ctx

from flask import jsonify, render_template, request

from core.runtime import get_default_runtime, get_runtime
from services.energy import (
    build_energy_overview,
    get_energy_history,
    get_energy_settings,
    get_runtime_energy_snapshot,
    reset_runtime_today,
    reset_runtime_total,
    reset_today_all_runtimes,
    reset_total_all_runtimes,
    update_energy_settings,
)


def _runtime_or_error(tent_id):
    try:
        return get_runtime(tent_id), None
    except (KeyError, ValueError):
        return None, (jsonify(success=False, error="tent_not_found"), 404)


def _reset_response(runtime, mode, device=None):
    try:
        if mode == "today":
            targets = reset_runtime_today(runtime, device=device)
        else:
            targets = reset_runtime_total(runtime, device=device)
    except ValueError as exc:
        return jsonify(success=False, error=str(exc)), 400

    return jsonify({
        "success": True,
        "tent_id": runtime.tent_id,
        "device": device,
        "targets": targets,
        "mode": mode,
    })


def register(app):

    @app.route("/energie/diagramme")
    def energie_diagramme_page():
        return render_template("energie_diagramme.html")

    # ------------------------------------------------------------------
    # Legacy/default-station compatibility
    # ------------------------------------------------------------------
    @app.route("/api/energy")
    def api_energy():
        # Existing consumers keep receiving the default station's device map.
        return jsonify(get_runtime_energy_snapshot(get_default_runtime()))

    @app.route("/api/energy/reset_total/<device>", methods=["POST"])
    def api_energy_reset_total_device(device):
        return _reset_response(get_default_runtime(), "total", device)

    @app.route("/api/energy/reset_today/<device>", methods=["POST"])
    def api_energy_reset_today_device(device):
        return _reset_response(get_default_runtime(), "today", device)

    # ------------------------------------------------------------------
    # New controller-wide + per-station API
    # ------------------------------------------------------------------
    @app.route("/api/energy/overview")
    def api_energy_overview():
        return jsonify(build_energy_overview())

    @app.route("/api/energy/history")
    def api_energy_history():
        range_key = request.args.get("range", "today")
        try:
            return jsonify(get_energy_history(range_key))
        except ValueError as exc:
            return jsonify(success=False, error=str(exc)), 400

    @app.route("/api/energy/settings", methods=["GET", "POST"])
    def api_energy_settings():
        if request.method == "GET":
            return jsonify({
                "success": True,
                "settings": get_energy_settings(),
            })

        data = request.get_json(silent=True) or {}
        try:
            result = update_energy_settings(data)
        except (TypeError, ValueError) as exc:
            return jsonify(success=False, error=str(exc)), 400

        return jsonify(success=True, **result)

    @app.route("/api/tents/<tent_id>/energy")
    def api_tent_energy(tent_id):
        runtime, error = _runtime_or_error(tent_id)
        if error:
            return error

        overview = build_energy_overview([runtime])
        station = overview["stations"][0] if overview["stations"] else None
        return jsonify({
            "success": True,
            "station": station,
            "settings": overview["settings"],
        })

    @app.route(
        "/api/tents/<tent_id>/energy/reset_today/<device>",
        methods=["POST"],
    )
    def api_tent_energy_reset_today_device(tent_id, device):
        runtime, error = _runtime_or_error(tent_id)
        if error:
            return error
        return _reset_response(runtime, "today", device)

    @app.route(
        "/api/tents/<tent_id>/energy/reset_total/<device>",
        methods=["POST"],
    )
    def api_tent_energy_reset_total_device(tent_id, device):
        runtime, error = _runtime_or_error(tent_id)
        if error:
            return error
        return _reset_response(runtime, "total", device)

    @app.route(
        "/api/tents/<tent_id>/energy/reset_today_all",
        methods=["POST"],
    )
    def api_tent_energy_reset_today_all(tent_id):
        runtime, error = _runtime_or_error(tent_id)
        if error:
            return error
        return _reset_response(runtime, "today")

    @app.route(
        "/api/tents/<tent_id>/energy/reset_total_all",
        methods=["POST"],
    )
    def api_tent_energy_reset_total_all(tent_id):
        runtime, error = _runtime_or_error(tent_id)
        if error:
            return error
        return _reset_response(runtime, "total")

    # Existing controller-wide ALL routes now intentionally mean ALL loaded
    # stations.  Per-station reset endpoints above are available for narrower
    # operations.
    @app.route("/api/energy/reset_total_all", methods=["POST"])
    def api_energy_reset_total_all():
        changed = reset_total_all_runtimes()
        print("🧹 ENERGY: Manueller Total-Reset aller Stationen")
        return jsonify(success=True, scope="controller", stations=changed)

    @app.route("/api/energy/reset_today_all", methods=["POST"])
    def api_energy_reset_today_all():
        changed = reset_today_all_runtimes()
        print("🧹 ENERGY: Manueller Today-Reset aller Stationen")
        return jsonify(success=True, scope="controller", stations=changed)
