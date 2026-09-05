# routes/watchdog.py

import datetime
import os

from flask import jsonify, render_template, request, send_file

import core.context as ctx

from core.watchdog_health import build_watchdog_snapshot
from core.system_metrics import build_system_metrics
from services.watchdog import log_event


def _safe_int_arg(name, default, minimum=1, maximum=5000):
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def register(app):

    @app.route("/grow-control/watchdog/systemdaten")
    def watchdog_system_data():
        return render_template("system_metrics.html")

    @app.route("/api/watchdog/log")
    def api_watchdog_log():
        lines = _safe_int_arg("lines", 300)
        level = str(request.args.get("level", "ALL") or "ALL").upper()
        if level not in {"ALL", "INFO", "WARN", "ERROR"}:
            level = "ALL"

        if not os.path.exists(ctx.LOG_FILE):
            return jsonify({"lines": []})

        try:
            with open(ctx.LOG_FILE, "r", encoding="utf-8") as f:
                all_lines = f.readlines()

            if level == "ALL":
                filtered = all_lines
            else:
                filtered = [line for line in all_lines if f"{level}:" in line]

            return jsonify({"lines": filtered[-lines:]})

        except Exception as exc:
            return jsonify({"lines": [f"❌ Fehler beim Lesen: {exc}"]})

    @app.route("/api/watchdog/log/clear", methods=["POST"])
    def api_watchdog_log_clear():
        try:
            os.makedirs(os.path.dirname(ctx.LOG_FILE) or ".", exist_ok=True)
            with open(ctx.LOG_FILE, "w", encoding="utf-8"):
                pass

            log_event("Log wurde manuell geleert")
            return jsonify(status="ok")

        except Exception as exc:
            return jsonify(status="error", message=str(exc)), 500

    @app.route("/api/watchdog/log/download")
    def api_watchdog_log_download():
        if not os.path.exists(ctx.LOG_FILE):
            return jsonify(error="Kein Log vorhanden"), 404

        return send_file(
            ctx.LOG_FILE,
            as_attachment=True,
            download_name="infolog.txt",
        )

    @app.route("/api/watchdog/status")
    def api_watchdog_status():
        snapshot = build_watchdog_snapshot()
        snapshot["time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return jsonify(snapshot)

    @app.route("/api/watchdog/systemdaten")
    def api_watchdog_system_data():
        return jsonify(build_system_metrics())
