from flask import jsonify, render_template, request

from auth.decorators import permission_required
from core.config_update import apply_config_patch, config_snapshot
from core.runtime import get_default_runtime
from services.network import (
    NetworkChangeError,
    connect_wifi,
    get_current_wifi_password,
    network_permissions,
    network_provisioning_secret_status,
    network_status,
    save_current_wifi_provisioning_secret,
    update_current_wifi_password,
    wifi_scan,
)


def register(app):

    @app.route("/system/network")
    @permission_required("settings.view")
    def system_network_page():
        return render_template("network.html")

    @app.route("/api/config/network/status")
    @permission_required("settings.view")
    def api_network_status():
        return jsonify(network_status())

    @app.route("/api/config/network/wifi")
    @permission_required("settings.view")
    def api_network_wifi():
        force = str(request.args.get("refresh") or "").strip().lower() in {
            "1", "true", "yes", "on"
        }
        return jsonify(wifi_scan(force=force))

    @app.route("/api/config/network/capabilities")
    @permission_required("settings.view")
    def api_network_capabilities():
        return jsonify(network_permissions())

    @app.route("/api/config/network/provisioning-secret")
    @permission_required("settings.view")
    def api_network_provisioning_secret():
        response = jsonify(
            network_provisioning_secret_status()
        )
        response.headers["Cache-Control"] = "no-store, private, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.route("/system/network/provisioning-secret", methods=["POST"])
    @permission_required("settings.manage")
    def system_network_provisioning_secret():
        data = request.get_json(silent=True) or {}

        try:
            result = save_current_wifi_provisioning_secret(
                data.get("password")
            )
        except ValueError as exc:
            return jsonify(
                success=False,
                error=str(exc),
            ), 400
        except NetworkChangeError as exc:
            return jsonify(exc.as_dict()), 409
        except RuntimeError as exc:
            return jsonify(
                success=False,
                error=str(exc),
            ), 503

        response = jsonify(result)
        response.headers["Cache-Control"] = "no-store, private, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    # Absichtlich unter /system: Die bestehende zentrale Auth-Policy verlangt
    # für schreibende /system-Unterpfade bereits settings.manage.
    @app.route("/system/network/connect", methods=["POST"])
    @permission_required("settings.manage")
    def system_network_connect():
        data = request.get_json(silent=True) or {}

        try:
            result = connect_wifi(
                data.get("ssid"),
                data.get("password"),
            )
        except ValueError as exc:
            return jsonify(
                success=False,
                error=str(exc),
            ), 400
        except NetworkChangeError as exc:
            return jsonify(exc.as_dict()), 409
        except RuntimeError as exc:
            return jsonify(
                success=False,
                error=str(exc),
            ), 503

        return jsonify(result)

    @app.route("/system/network/password", methods=["POST"])
    @permission_required("settings.manage")
    def system_network_password():
        data = request.get_json(silent=True) or {}

        try:
            result = update_current_wifi_password(
                data.get("ssid"),
                data.get("password"),
            )
        except ValueError as exc:
            return jsonify(
                success=False,
                error=str(exc),
            ), 400
        except NetworkChangeError as exc:
            return jsonify(exc.as_dict()), 409
        except RuntimeError as exc:
            return jsonify(
                success=False,
                error=str(exc),
            ), 503

        return jsonify(result)

    # Prüft erst, ob NetworkManager eine Passphrase oder nur einen
    # abgeleiteten 64-Hex-PSK gespeichert hat.
    @app.route("/system/network/password/show", methods=["POST"])
    @permission_required("settings.manage")
    def system_network_password_show():
        data = request.get_json(silent=True) or {}

        try:
            result = get_current_wifi_password(data.get("ssid"))
        except ValueError as exc:
            response = jsonify(success=False, error=str(exc))
            response.status_code = 400
        except NetworkChangeError as exc:
            response = jsonify(exc.as_dict())
            response.status_code = 409
        except RuntimeError as exc:
            response = jsonify(success=False, error=str(exc))
            response.status_code = 503
        else:
            response = jsonify(result)

        response.headers["Cache-Control"] = "no-store, private, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

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
