from flask import jsonify, request, send_file

import sqlite3
import time

from core.tents import DEFAULT_TENT_ID, manager as tent_manager, validate_tent_id


_RANGE_MAP = {
    "1h": 1 * 3600,
    "6h": 6 * 3600,
    "24h": 24 * 3600,
    "7d": 7 * 24 * 3600,
}


def _validated_tent_id(tent_id):
    try:
        tent_id = validate_tent_id(tent_id)
    except ValueError:
        return None
    if tent_manager.get(tent_id) is None:
        return None
    return tent_id


def _history_rows(tent_id, range_key, data_type):
    seconds = _RANGE_MAP.get(range_key, 24 * 3600)
    since = int(time.time()) - seconds

    db = sqlite3.connect("data.db")
    c = db.cursor()

    try:
        if data_type == "temp":
            c.execute(
                """
                SELECT ts, temp, temp_target
                FROM temp_history
                WHERE tent_id = ? AND ts >= ?
                ORDER BY ts ASC
                """,
                (tent_id, since),
            )
            return [
                {"ts": r[0], "temp": r[1], "target": r[2]}
                for r in c.fetchall()
                if r[1] is not None
            ]

        if data_type == "hum":
            c.execute(
                """
                SELECT ts, hum, hum_target
                FROM temp_history
                WHERE tent_id = ? AND ts >= ?
                ORDER BY ts ASC
                """,
                (tent_id, since),
            )
            return [
                {"ts": r[0], "hum": r[1], "target": r[2]}
                for r in c.fetchall()
                if r[1] is not None
            ]

        if data_type == "vpd":
            c.execute(
                """
                SELECT ts, vpd
                FROM temp_history
                WHERE tent_id = ? AND ts >= ?
                ORDER BY ts ASC
                """,
                (tent_id, since),
            )
            return [
                {"ts": r[0], "vpd": r[1]}
                for r in c.fetchall()
                if r[1] is not None
            ]

        return []
    finally:
        db.close()


def register(app):

    @app.route("/api/history")
    def api_history():
        """Legacy-Verlauf für tent_1."""
        return jsonify(
            _history_rows(
                DEFAULT_TENT_ID,
                request.args.get("range", "24h"),
                request.args.get("type", "temp"),
            )
        )

    @app.route("/api/tents/<tent_id>/history")
    def api_tent_history(tent_id):
        tent_id = _validated_tent_id(tent_id)
        if not tent_id:
            return jsonify(success=False, error="tent_not_found"), 404

        return jsonify(
            _history_rows(
                tent_id,
                request.args.get("range", "24h"),
                request.args.get("type", "temp"),
            )
        )

    @app.route("/api/reset_history", methods=["POST"])
    def api_reset_history():
        """Legacy: löscht weiterhin bewusst die komplette Historie."""
        try:
            db = sqlite3.connect("data.db")
            c = db.cursor()
            c.execute("DELETE FROM temp_history")
            db.commit()
            db.close()
            print("🧹 Diagramm-Historie zurückgesetzt")
            return jsonify(status="ok", message="Diagramm-Historie gelöscht")
        except Exception as exc:
            print("❌ Reset Fehler:", exc)
            return jsonify(status="error", message=str(exc)), 500

    @app.route("/api/tents/<tent_id>/history/reset", methods=["POST"])
    def api_tent_reset_history(tent_id):
        tent_id = _validated_tent_id(tent_id)
        if not tent_id:
            return jsonify(success=False, error="tent_not_found"), 404

        try:
            db = sqlite3.connect("data.db")
            c = db.cursor()
            c.execute("DELETE FROM temp_history WHERE tent_id = ?", (tent_id,))
            db.commit()
            db.close()
            print(f"🧹 [{tent_id}] Diagramm-Historie zurückgesetzt")
            return jsonify(status="ok", tent_id=tent_id)
        except Exception as exc:
            return jsonify(status="error", message=str(exc)), 500

    @app.route("/api/diagrams/export")
    def export_diagrams():
        return send_file(
            "data.db",
            as_attachment=True,
            download_name="grow_diagrams.db",
        )

    @app.route("/api/diagrams/import", methods=["POST"])
    def import_diagrams():
        with open("data.db", "wb") as f:
            f.write(request.data)
        return {"status": "ok"}
