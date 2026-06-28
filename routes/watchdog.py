import datetime
import os
import time

from flask import jsonify, request, send_file

import core.state as state
import core.context as ctx

from core.constants import SENSOR_TIMEOUT
from services.watchdog import log_event

def register(app):

    @app.route("/api/watchdog/log")
    def api_watchdog_log():

        lines = int(request.args.get("lines", 300))
        level = request.args.get("level", "ALL")

        if not os.path.exists(ctx.LOG_FILE):
            return jsonify({"lines": []})

        try:
            with open(ctx.LOG_FILE, "r") as f:
                all_lines = f.readlines()

            filtered = []

            for line in all_lines:

                if level == "ALL":
                    filtered.append(line)

                elif f"{level}:" in line:
                    filtered.append(line)

            return jsonify({
                "lines": filtered[-lines:]
            })

        except Exception as e:

            return jsonify({
                "lines": [f"❌ Fehler beim Lesen: {e}"]
            })

    @app.route("/api/watchdog/log/clear", methods=["POST"])
    def api_watchdog_log_clear():

        try:

            open(ctx.LOG_FILE, "w").close()

            log_event("Log wurde manuell geleert")

            return {"status": "ok"}

        except Exception as e:

            return {
                "status": "error",
                "message": str(e)
            }, 500

    @app.route("/api/watchdog/log/download")
    def api_watchdog_log_download():

        if not os.path.exists(ctx.LOG_FILE):
            return {"error": "Kein Log vorhanden"}, 404

        return send_file(
            ctx.LOG_FILE,
            as_attachment=True,
            download_name="infolog.txt"
        )

    @app.route("/api/watchdog/status")
    def api_watchdog_status():

        now = time.time()

        with ctx.state_lock:

            ds_age = (
                now - state.last_ds_time
                if state.last_ds_time
                else 999999
            )

            dht_age = (
                now - state.last_dht_time
                if state.last_dht_time
                else 999999
            )

        with ctx.energy_lock:
            energy = dict(ctx.energy_state)
        
        ecount = len(energy)

        mqtt_age = (
            now - ctx.MQTT_LAST_MSG
            if ctx.MQTT_LAST_MSG
            else 999999
        )

        return jsonify({

            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

            "temp": {
                "age": int(ds_age),
                "stale": ds_age > SENSOR_TIMEOUT
            },

            "hum": {
                "age": int(dht_age),
                "stale": dht_age > SENSOR_TIMEOUT
            },

            "mqtt": {
                "age": int(mqtt_age),
                "stale": mqtt_age > 30
            },

            "energy": {
                "devices": ecount,
                "stale": ecount == 0
            }
        })
