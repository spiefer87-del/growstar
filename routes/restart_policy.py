"""Setup-Seite und API für das Neustart-Verhalten pro Aktor."""

from flask import jsonify, render_template, request

from core.restart_policy import (
    restart_policy_snapshot,
    update_restart_policy,
)
from core.runtime import get_runtime
from core.tents import manager as tent_manager, validate_tent_id


def _runtime_or_error(tent_id):
    try:
        tent_id = validate_tent_id(tent_id)
    except ValueError:
        return None, (jsonify(success=False, error="invalid_tent_id"), 400)

    if tent_manager.get(tent_id) is None:
        return None, (jsonify(success=False, error="tent_not_found"), 404)

    try:
        return get_runtime(tent_id), None
    except KeyError:
        return None, (
            jsonify(
                success=False,
                error="tent_runtime_not_loaded",
                message=(
                    "Die Station ist aktuell nicht als Runtime geladen. "
                    "Aktiviere sie zunächst im Setup."
                ),
            ),
            409,
        )


def register(app):

    @app.route("/grow-control/setup/restart-policy")
    def grow_control_restart_policy():
        return render_template("restart_policy.html")

    @app.route(
        "/api/tents/<tent_id>/restart-policy",
        methods=["GET", "PATCH"],
    )
    def api_tent_restart_policy(tent_id):
        runtime, error = _runtime_or_error(tent_id)
        if error:
            return error

        if request.method == "GET":
            return jsonify(restart_policy_snapshot(runtime))

        data = request.get_json(silent=True) or {}
        values = data.get("policy", data)

        try:
            result = update_restart_policy(
                values,
                runtime=runtime,
            )
        except (TypeError, ValueError) as exc:
            return jsonify(
                success=False,
                error=str(exc),
            ), 400

        return jsonify(result)
