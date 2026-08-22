"""HTTP API for capability routing metadata.

SF.4A is intentionally a configuration-only control plane. POST persists
assignments locally but does not send any command to Shelly or Spider Farmer.
"""

from flask import jsonify, request

from core.capability_routing import (
    CapabilityRouteConflictError,
    capability_routing_snapshot,
    control_target_inventory,
    update_capability_routes,
)


def register(app):

    @app.get("/api/control-targets")
    def api_control_targets():
        return jsonify(control_target_inventory())

    @app.route(
        "/api/tents/<tent_id>/capability-routing",
        methods=["GET", "POST"],
    )
    def api_capability_routing(tent_id):
        try:
            if request.method == "GET":
                return jsonify(
                    capability_routing_snapshot(tent_id)
                )

            data = request.get_json(silent=True) or {}
            return jsonify(
                update_capability_routes(
                    tent_id,
                    data,
                )
            )

        except CapabilityRouteConflictError as exc:
            return jsonify(
                success=False,
                error="capability_route_conflict",
                message=str(exc),
                capability=exc.capability,
                target_id=exc.target_id,
                owner=exc.owner,
                contender=exc.contender,
            ), 409

        except KeyError:
            return jsonify(
                success=False,
                error="tent_not_found",
            ), 404

        except (TypeError, ValueError) as exc:
            return jsonify(
                success=False,
                error="invalid_capability_route",
                message=str(exc),
            ), 400
