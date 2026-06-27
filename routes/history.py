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
