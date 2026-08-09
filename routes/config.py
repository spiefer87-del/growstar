from flask import jsonify, request

from core.config_update import apply_config_patch, config_snapshot
from core.runtime import get_default_runtime


def register(app):

    @app.route("/api/config", methods=["GET", "POST"])
    def api_config():
        """Legacy-API für tent_1.

        Neue Grow-Control-Seiten verwenden /api/tents/<tent_id>/config. Diese
        Route bleibt für bestehende Clients vollständig erhalten und benutzt
        intern denselben Runtime-basierten Update-Pfad.
        """

        runtime = get_default_runtime()

        if request.method == "GET":
            return jsonify(config_snapshot(runtime))

        data = request.get_json(silent=True) or {}
        try:
            result = apply_config_patch(data, runtime=runtime)
        except (TypeError, ValueError) as exc:
            return jsonify(status="error", error=str(exc)), 400

        return jsonify({
            "status": "ok",
            "config": result["config"],
            "changed_keys": result["changed_keys"],
        })
