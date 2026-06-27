from flask import send_file, request

import time
import sqlite3

from flask import jsonify, request


def register(app):

    @app.route("/api/history")
    def api_history():

        range_map = {
            "1h": 1 * 3600,
            "6h": 6 * 3600,
            "24h": 24 * 3600,
            "7d": 7 * 24 * 3600,
        }

        range_key = request.args.get("range", "24h")
        data_type = request.args.get("type", "temp")

        seconds = range_map.get(range_key, 24 * 3600)
        since = int(time.time()) - seconds

        db = sqlite3.connect("data.db")
        c = db.cursor()

        if data_type == "temp":

            c.execute("""
                SELECT ts, temp, temp_target
                FROM temp_history
                WHERE ts >= ?
                ORDER BY ts ASC
            """, (since,))

            rows = c.fetchall()

            data = [
                {
                    "ts": r[0],
                    "temp": r[1],
                    "target": r[2]
                }
                for r in rows
                if r[1] is not None
            ]

        elif data_type == "hum":

            c.execute("""
                SELECT ts, hum, hum_target
                FROM temp_history
                WHERE ts >= ?
                ORDER BY ts ASC
            """, (since,))

            rows = c.fetchall()

            data = [
                {
                    "ts": r[0],
                    "hum": r[1],
                    "target": r[2]
                }
                for r in rows
                if r[1] is not None
            ]

        elif data_type == "vpd":

            c.execute("""
                SELECT ts, vpd
                FROM temp_history
                WHERE ts >= ?
                ORDER BY ts ASC
            """, (since,))

            rows = c.fetchall()

            data = [
                {
                    "ts": r[0],
                    "vpd": r[1]
                }
                for r in rows
                if r[1] is not None
            ]

        else:
            data = []

        db.close()

        return jsonify(data)

    @app.route("/api/reset_history", methods=["POST"])
    def api_reset_history():
        try:
            db = sqlite3.connect("data.db")
            c = db.cursor()
    
            c.execute("DELETE FROM temp_history")
    
            db.commit()
            db.close()
    
            print("🧹 Diagramm-Historie zurückgesetzt")
    
            return jsonify({
                "status": "ok",
                "message": "Diagramm-Historie gelöscht"
            })
    
        except Exception as e:
            print("❌ Reset Fehler:", e)
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @app.route("/api/diagrams/export")
    def export_diagrams():
        return send_file(
            "data.db",
            as_attachment=True,
            download_name="grow_diagrams.db"
        )

    @app.route("/api/diagrams/import", methods=["POST"])
    def import_diagrams():
        with open("data.db", "wb") as f:
            f.write(request.data)

        return {
            "status": "ok"
        }
